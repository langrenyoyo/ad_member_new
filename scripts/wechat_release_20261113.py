"""Read local credentials without logging secrets; deploy only on explicit CLI action."""
from pathlib import Path
import re, json, sys, paramiko

ROOT=Path(__file__).resolve().parents[1]
REMOTE='/www/wwwroot/ad_member_new'
def configuration():
    raw=(ROOT/'serverdata.md').read_text(encoding='utf-8')
    def field(key):
        match=re.search(r'^'+re.escape(key)+r'\s*[:：]\s*(\S+)',raw,re.M|re.I)
        if not match: raise ValueError('Missing field: '+key)
        return match.group(1)
    return {'host':field('IP'),'user':field('user'),'password':field('password'),
        'appid':re.search(r'APPID\s*[:：]\s*(wx[a-zA-Z0-9]+)',raw,re.I).group(1),
        'secret':re.search(r'AppSecret\s*[:：]\s*([a-zA-Z0-9]+)',raw,re.I).group(1),
        'package':re.search(r'应用包名\s*[:：]\s*([a-zA-Z0-9_.]+)',raw).group(1),
        'md5':re.search(r'应用签名\s*[:：]\s*([a-fA-F0-9]{32})',raw).group(1).lower(),
        'game_id':int(re.search(r'业务游戏\s*ID\s*[:：]\s*(\d+)',raw,re.I).group(1))}

def connect(c):
    client=paramiko.SSHClient();client.load_system_host_keys()
    client.connect(c['host'],username=c['user'],password=c['password'],look_for_keys=False,allow_agent=False,timeout=20)
    return client

def run(client,program):
    inp,out,err=client.exec_command(REMOTE+'/.venv/bin/python -',timeout=180)
    inp.write(program);inp.flush();inp.channel.shutdown_write()
    stdout=out.read().decode();stderr=err.read().decode();code=out.channel.recv_exit_status()
    if code: raise RuntimeError('Remote action failed: '+stderr[-1800:])
    print(stdout)
    return stdout

if __name__=='__main__':
    c=configuration()
    print(json.dumps({k:c[k] for k in ['appid','package','md5','game_id']}))
    client=connect(c)
    try:
        run(client,r'''
import subprocess,json,sqlite3,urllib.request
from pathlib import Path
root=Path('/www/wwwroot/ad_member_new')
def git(*args):return subprocess.check_output(['git','-c','safe.directory='+str(root),'-C',str(root),*args],text=True).strip()
print(json.dumps({'branch':git('branch','--show-current'),'head':git('rev-parse','HEAD'),'status':git('status','--short'),'service':subprocess.check_output(['systemctl','is-active','ad-member-new.service'],text=True).strip()}))
print(subprocess.check_output(['systemctl','show','ad-member-new.service','-p','ExecStart','-p','WorkingDirectory','-p','EnvironmentFiles'],text=True))
with sqlite3.connect('file:'+str(root/'backend/app.db')+'?mode=ro',uri=True) as db:
 print('game_columns', [x[1] for x in db.execute('pragma table_info(games)')])
 print('migration',db.execute('select version_num from alembic_version').fetchall())
with urllib.request.urlopen('http://127.0.0.1:8001/api/health',timeout=10) as response:print('health',response.status)
''')
    finally: client.close()
