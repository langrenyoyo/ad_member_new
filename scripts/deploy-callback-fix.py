"""Deploy the callback response/audit fix only, retaining a server-side backup."""
from pathlib import Path
import datetime
import re
import paramiko

root=Path(__file__).resolve().parents[1]
source=(root/'serverdata.md').read_text(encoding='utf-8')
def field(name):return re.search(r'^'+name+r'\s*[:：]\s*(\S+)',source,re.M).group(1)
client=paramiko.SSHClient();client.load_system_host_keys()
client.connect(field('IP'),username=field('user'),password=field('password'),look_for_keys=False,allow_agent=False,timeout=10)
remote='/www/wwwroot/ad_member_new/backend/app/main_from_txt.py'
backup=remote+'.before-callback-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
def run(command):
 _,out,err=client.exec_command(command,timeout=60)
 value=out.read().decode();error=err.read().decode()
 if out.channel.recv_exit_status():raise RuntimeError(error)
 print(value)
try:
 run('cp -p '+remote+' '+backup)
 client.open_sftp().put(str(root/'backend/app/main_from_txt.py'),remote+'.pending')
 run('/www/wwwroot/ad_member_new/.venv/bin/python -m py_compile '+remote+'.pending')
 run('mv '+remote+'.pending '+remote+' && systemctl restart ad-member-new.service')
 run('curl --retry 8 --retry-connrefused --retry-delay 1 -fsS http://127.0.0.1:8001/api/health')
 run("curl -sS -i http://127.0.0.1:8001/api/callbacks/taku/reward")
 print('Backup: '+backup)
finally:client.close()
