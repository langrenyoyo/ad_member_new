"""Validate and sync documented eCPM keys without logging secret material."""
import json
import re
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'serverdata.md').read_text(encoding='utf-8')

def field(name):
    match = re.search(r'^' + re.escape(name) + r'\s*[:：]\s*(\S+)', source, re.M)
    if not match:
        raise ValueError('Missing document field: ' + name)
    return match.group(1)

payload = {}
for kind, label in [('server', '服务端'), ('client', '客户端')]:
    match = re.search(re.escape(label) + r'eCPM Key\s*[:：]\s*(-----BEGIN (?:RSA )?PRIVATE KEY-----.*?-----END (?:RSA )?PRIVATE KEY-----)', source, re.S)
    if not match:
        raise ValueError('Missing PEM: ' + kind)
    payload[kind] = {'id': field(label + 'eCPM Key ID'), 'pem': match.group(1)}

remote_code = r'''
import sys,json,os,datetime,shutil
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
sys.path.insert(0,'/www/wwwroot/ad_member_new/backend')
from app import main_from_txt as m
from app.taku_ecpm import _keyring, _game_keys, require_configuration
data=json.load(sys.stdin)
for item in data.values():
 key=serialization.load_pem_private_key(item['pem'].encode(),password=None)
 assert isinstance(key,rsa.RSAPrivateKey), 'Expected RSA key'
 item['pem']=key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()).decode()
 print('DOCUMENT_KEY_VALID',key.key_size)
assert data['server']['id'] != data['client']['id'] or data['server']['pem']==data['client']['pem'], 'Conflicting document Key IDs'
ring=_keyring()
override=ring.get('238')
print('GAME_OVERRIDE',override is not None)
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
backup=Path('/www/backup/ecpm-'+stamp)
backup.mkdir(mode=0o700,parents=True)
with m.SessionLocal() as s:
 s.execute(m.text('BEGIN IMMEDIATE'))
 row=s.get(m.TakuGlobalConfig,1)
 assert row is not None,'Global config missing'
 old={kind:json.loads(getattr(row,kind+'_ecpm_key') or '{}') for kind in data}
 snapshot=backup/'global-ecpm.json'
 fd=os.open(str(snapshot),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'w') as f:json.dump(old,f)
 for kind,item in data.items():
  existing=old[kind].get(item['id'])
  print('GLOBAL_MATCH',kind,existing==item['pem'])
  # Explicit document sync retains other rotation IDs, replacing the specified ID only.
  old[kind][item['id']]=item['pem']
  setattr(row,kind+'_ecpm_key',json.dumps(old[kind]))
 if override is not None:
  filename=Path(os.environ['TAKU_ECPM_KEYRING_FILE'])
  shutil.copy2(filename,backup/'keyring.json')
  os.chmod(backup/'keyring.json',0o600)
  for kind,item in data.items():
   print('OVERRIDE_MATCH',kind,override['keys'].get(item['id'])==item['pem'])
   override['keys'][item['id']]=item['pem']
  pending=filename.with_name(filename.name+'.pending-'+stamp)
  fd=os.open(str(pending),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
  with os.fdopen(fd,'w') as f:json.dump(ring,f)
  st=filename.stat();os.chown(pending,st.st_uid,st.st_gid);os.chmod(pending,st.st_mode & 0o777)
  os.replace(pending,filename)
 s.commit()
assert require_configuration(238,required=True)
effective=_game_keys(238)['keys']
for kind,item in data.items():
 assert effective[item['id']]==item['pem']
 print('EFFECTIVE_MATCH',kind,True)
print('BACKUP',str(backup))
'''

client = paramiko.SSHClient()
client.load_system_host_keys()
client.connect(field('IP'), username=field('user'), password=field('password'), look_for_keys=False, allow_agent=False, timeout=15)
try:
    with client.open_sftp() as sftp:
        with sftp.file('/tmp/ad-member-sync-ecpm.py', 'w') as f:
            f.write(remote_code)
    command = 'systemd-run --quiet --wait --pipe -p WorkingDirectory=/www/wwwroot/ad_member_new -p EnvironmentFile=/www/wwwroot/ad_member_new/.env /www/wwwroot/ad_member_new/.venv/bin/python /tmp/ad-member-sync-ecpm.py'
    stdin, stdout, stderr = client.exec_command(command, timeout=60)
    stdin.write(json.dumps(payload)); stdin.flush(); stdin.channel.shutdown_write()
    output=stdout.read().decode(); error=stderr.read().decode()
    print(output)
    if stdout.channel.recv_exit_status():
        # Tracebacks may include data; disclose only the last exception type.
        raise RuntimeError('Remote sync failed: ' + (error.splitlines()[-1].split(':')[0] if error else 'unknown'))
    _, out, err = client.exec_command('curl -fsS http://127.0.0.1:8001/api/health', timeout=15)
    print('HEALTH', out.read().decode())
    if out.channel.recv_exit_status():
        raise RuntimeError('Health check failed')
finally:
    client.close()
