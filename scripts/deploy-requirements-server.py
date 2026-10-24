"""Deploy the reviewed admin/backend requirement files with a server backup."""
from pathlib import Path
import datetime
import json
import re
import subprocess
import paramiko

root = Path(__file__).resolve().parents[1]
source = (root/'serverdata.md').read_text(encoding='utf-8')
def field(name):
    return re.search(r'^'+name+r'\s*[:：]\s*(\S+)', source, re.M).group(1)

files = subprocess.check_output(['git','diff','--name-only','--','backend/app','public'],cwd=root,text=True).splitlines()
files += ['backend/alembic/versions/e937_member_whitelist_coin_range.py',
          'backend/alembic/versions/e938_three_member_roles.py',
          'public/admin-refinement.css','public/ad-config-layout.css']
stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
remote = '/www/wwwroot/ad_member_new'
backup = '/www/backup/ad-member-requirements-'+stamp
client = paramiko.SSHClient()
client.load_system_host_keys()
client.connect(field('IP'),username=field('user'),password=field('password'),
    look_for_keys=False,allow_agent=False,timeout=10,auth_timeout=10)
def run(command):
    _,out,err=client.exec_command(command,timeout=120)
    result=out.read().decode('utf-8',errors='replace')
    errors=err.read().decode('utf-8',errors='replace')
    code=out.channel.recv_exit_status()
    print(result)
    if code:
        print(errors)
        raise RuntimeError('Remote command failed with exit '+str(code))
    return result

try:
    status=run('cd '+remote+' && git -c safe.directory='+remote+' diff --name-only')
    if status.strip():
        raise RuntimeError('Tracked server changes require review')
    run('mkdir -p '+backup)
    sftp=client.open_sftp()
    bootstrap = '''import pathlib, shutil, sqlite3, json, sys
sys.path.insert(0, "BACKEND")
from app.main_from_txt import engine
target=pathlib.Path("BACKUP")
if engine.url.get_backend_name() != 'sqlite':
    raise RuntimeError('Database backup requires a database-specific procedure')
with sqlite3.connect(engine.url.database) as src, sqlite3.connect(str(target/'database.sqlite')) as dest:
    src.backup(dest)
for name in FILES:
    source=pathlib.Path("ROOT")/name
    if source.exists():
        dest=target/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
(target/'manifest.json').write_text(json.dumps(FILES))
print('Database and code backup complete')
'''.replace('BACKEND',remote+'/backend').replace('BACKUP',backup).replace('ROOT',remote).replace('FILES',repr(files))
    with sftp.file(backup+'/backup.py','w') as handle: handle.write(bootstrap)
    prefix='systemd-run --quiet --wait --pipe -p WorkingDirectory='+remote+' -p EnvironmentFile='+remote+'/.env '
    run(prefix+remote+'/.venv/bin/python '+backup+'/backup.py')
    for name in files:
        sftp.put(str(root/name),remote+'/'+name+'.deploy-temp')
    run('systemctl stop ad-member-new.service')
    try:
        for name in files:
            sftp.posix_rename(remote+'/'+name+'.deploy-temp',remote+'/'+name)
        run(prefix+remote+'/.venv/bin/python -m alembic upgrade head')
    finally:
        run('systemctl start ad-member-new.service')
    run('curl --retry 8 --retry-connrefused --retry-delay 1 -fsS http://127.0.0.1:8001/api/health')
    run('systemctl start taku-report-sync@238.service && journalctl -u taku-report-sync@238.service -n 6 --no-pager')
    print('Backup: '+backup)
finally:
    client.close()
