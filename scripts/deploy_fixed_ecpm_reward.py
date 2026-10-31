"""Deploy only the fixed-price proof identity correction, with rollback."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import paramiko


ROOT = Path(__file__).resolve().parents[1]
REMOTE = '/www/wwwroot/ad_member_new'
TARGET = 'backend/app/main_from_txt.py'
EXPECTED = 'ed85c66e4b64be92b85a673dcc9188863bae71307695cd4fe8b6190756232c0b'


def main():
    credentials = {}
    for line in (ROOT / 'serverdata.md').read_text(encoding='utf-8').splitlines():
        key, separator, value = line.partition(':')
        if separator and key.strip() in ('IP', 'user', 'password'):
            credentials[key.strip()] = value.strip()
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.connect(credentials['IP'], username=credentials['user'],
                   password=credentials['password'], look_for_keys=False,
                   allow_agent=False, timeout=10, auth_timeout=10)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = '/www/backup/ad-member-fixed-ecpm-' + stamp
    pending = REMOTE + '/' + TARGET + '.fixed-ecpm-' + stamp
    expected_new = hashlib.sha256((ROOT / TARGET).read_bytes()).hexdigest()
    program = r'''
import hashlib, json, os, pathlib, py_compile, shutil, sqlite3, subprocess
root = pathlib.Path(CONFIG['root'])
target = root / CONFIG['target']
pending = pathlib.Path(CONFIG['pending'])
backup = pathlib.Path(CONFIG['backup'])
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def health():
    subprocess.run(['curl','--retry','8','--retry-connrefused','--retry-delay','1',
                    '-fsS','http://127.0.0.1:8001/api/health'],check=True,capture_output=True)
try:
    if digest(target) != CONFIG['expected']:
        raise RuntimeError('Server source changed; deployment aborted')
    if digest(pending) != CONFIG['new']:
        raise RuntimeError('Uploaded source hash mismatch')
    health()
    py_compile.compile(str(pending), doraise=True)
    backup.mkdir(mode=0o700)
    shutil.copy2(target, backup/'main_from_txt.py')
    with sqlite3.connect('file:'+str(root/'backend/app.db')+'?mode=ro',uri=True) as src:
        with sqlite3.connect(str(backup/'database-before.sqlite')) as dst:
            src.backup(dst)
    st = target.stat()
    os.chmod(pending, st.st_mode)
    os.chown(pending, st.st_uid, st.st_gid)
    subprocess.run(['systemctl','stop','ad-member-new'],check=True)
    try:
        os.replace(pending, target)
        subprocess.run(['systemctl','start','ad-member-new'],check=True)
        health()
        assert digest(target) == CONFIG['new']
    except BaseException:
        subprocess.run(['systemctl','stop','ad-member-new'],check=True)
        shutil.copy2(backup/'main_from_txt.py',target)
        os.chown(target,st.st_uid,st.st_gid)
        subprocess.run(['systemctl','start','ad-member-new'],check=True)
        health()
        raise
    report = {'backup':str(backup),'sha256':digest(target),'health':'ok',
              'service':subprocess.check_output(['systemctl','is-active','ad-member-new'],text=True).strip(),
              'files_changed':[CONFIG['target']]}
    (backup/'manifest.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report))
finally:
    if pending.exists(): pending.unlink()
'''
    config = dict(root=REMOTE, target=TARGET, pending=pending, backup=backup,
                  expected=EXPECTED, new=expected_new)
    try:
        with client.open_sftp() as sftp:
            sftp.put(str(ROOT / TARGET), pending)
        stdin, stdout, stderr = client.exec_command(REMOTE+'/.venv/bin/python -',timeout=120)
        stdin.write('CONFIG = '+repr(config)+'\n'+program)
        stdin.flush()
        stdin.channel.shutdown_write()
        output = stdout.read().decode('utf-8')
        error = stderr.read().decode('utf-8')
        code = stdout.channel.recv_exit_status()
        if code:
            raise RuntimeError('Deployment failed: '+error[-2000:])
        print(output)
    finally:
        client.close()


if __name__ == '__main__':
    main()
