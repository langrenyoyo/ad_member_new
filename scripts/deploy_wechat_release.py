"""Explicit release deployment. Credentials travel over SSH stdin, never Git/argv."""
from pathlib import Path
import subprocess,json
from wechat_release_20261113 import configuration,connect,run,ROOT

config=configuration()
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
client=connect(config)
program=r'''
import subprocess,json,sqlite3,os,time,urllib.request,shutil
from pathlib import Path
root=Path('/www/wwwroot/ad_member_new')
def git(*args):return subprocess.check_output(['git','-c','safe.directory='+str(root),'-C',str(root),*args],text=True).strip()
def service(action):subprocess.run(['systemctl',action,'ad-member-new.service'],check=True)
def health():
 for _ in range(25):
  try:
   with urllib.request.urlopen('http://127.0.0.1:8001/api/health',timeout=3) as r:
    if r.status==200:return
  except Exception:pass
  time.sleep(1)
 raise RuntimeError('health check failed')
assert git('status','--porcelain')=='', 'Server workspace changed'
assert git('branch','--show-current')=='main'
old=git('rev-parse','HEAD')
git('fetch','origin','main')
assert git('rev-parse','origin/main')==CONFIG['head'], 'Unexpected origin revision'
backup=Path('/www/backup/wechat-'+time.strftime('%Y%m%d-%H%M%S'));backup.mkdir(mode=0o700)
service('stop')
try:
 with sqlite3.connect(root/'backend/app.db') as db:
  with sqlite3.connect(backup/'database.sqlite') as dst:db.backup(dst)
 (backup/'previous-head').write_text(old)
 git('pull','--ff-only','origin','main')
 # Use the service's environment file for migration and database resolution.
 env=dict(os.environ)
 for line in (root/'.env').read_text().splitlines():
  line=line.strip()
  if line and not line.startswith('#') and '=' in line:
   key,value=line.split('=',1);env[key.strip()]=value.strip().strip('"').strip("'")
 result=subprocess.run([str(root/'.venv/bin/python'),'-m','alembic','-c',str(root/'alembic.ini'),'upgrade','head'],cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
 (backup/'migration.log').write_text(result.stdout)
 assert result.returncode==0, 'Migration failed; see protected backup log'
 # Deployment database was confirmed as SQLite during preflight.
 url=env.get('DATABASE_URL','')
 assert not url or url.startswith('sqlite:'), 'Unexpected database engine'
 if url:
  dbpath=Path(url.split('///',1)[1]);dbpath=dbpath if dbpath.is_absolute() else root/dbpath
  assert dbpath.resolve()==(root/'backend/app.db').resolve(), 'Unexpected database path'
 with sqlite3.connect(root/'backend/app.db') as db:
  row=db.execute('select status from games where id=?',(CONFIG['game_id'],)).fetchone()
  assert row and row[0]==1, 'Game is absent or disabled'
  db.execute('update games set wx_appid=?, wx_secert=? where id=?',(CONFIG['appid'],CONFIG['secret'],CONFIG['game_id']))
  db.commit()
 service('start');health()
 with sqlite3.connect(root/'backend/app.db') as db:
  row=db.execute('select wx_appid,wx_secert from games where id=?',(CONFIG['game_id'],)).fetchone()
  assert row==(CONFIG['appid'],CONFIG['secret'])
  revision=db.execute('select version_num from alembic_version').fetchone()[0]
 # The running process must reach WeChat code validation, not missing-config handling.
 request=urllib.request.Request('http://127.0.0.1:8001/api/app/v1/auth/wechat-login',data=json.dumps({'provider':'app','code':'deployment-invalid-code','game_id':CONFIG['game_id'],'device_id':'deployment-verification','platform':'android','app_version':'1.0.15'}).encode(),headers={'Content-Type':'application/json'})
 try:
  urllib.request.urlopen(request,timeout=15)
  raise RuntimeError('Invalid authorization code unexpectedly accepted')
 except urllib.error.HTTPError as e:
  auth_status=e.code;auth_body=json.loads(e.read())
  assert auth_status==401 and auth_body.get('detail')=='Invalid WeChat authorization code', 'Auth verification failed'
 print(json.dumps({'head':git('rev-parse','HEAD'),'backup':str(backup),'migration':revision,'game_id':CONFIG['game_id'],'appid':CONFIG['appid'],'secret_matches':True,'health':200,'auth_invalid_code_status':auth_status,'service':subprocess.check_output(['systemctl','is-active','ad-member-new.service'],text=True).strip()}))
except BaseException:
 service('stop')
 git('reset','--hard',old)
 if (backup/'database.sqlite').exists():
  with sqlite3.connect(backup/'database.sqlite') as src:
   with sqlite3.connect(root/'backend/app.db') as dst:src.backup(dst)
 service('start');health()
 raise
'''
try:
    data={k:config[k] for k in ['game_id','appid','secret']};data['head']=head
    output=run(client,'CONFIG='+repr(data)+'\n'+program)
    (ROOT/'artifacts/wechat-release-1.0.15/deployment.json').write_text(output,encoding='utf-8')
finally:client.close()
