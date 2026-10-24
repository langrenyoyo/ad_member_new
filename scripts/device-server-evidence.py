"""Read-only server evidence for the dedicated device test member."""
from pathlib import Path
import re
import paramiko

root=Path(__file__).resolve().parents[1]
source=(root/'serverdata.md').read_text(encoding='utf-8')
def field(name):return re.search(r'^'+name+r'\s*[:：]\s*(\S+)',source,re.M).group(1)
client=paramiko.SSHClient();client.load_system_host_keys()
client.connect(field('IP'),username=field('user'),password=field('password'),look_for_keys=False,allow_agent=False,timeout=10)
code='''import sys,json,subprocess,re
from urllib.parse import urlsplit,parse_qs
sys.path.insert(0,'/www/wwwroot/ad_member_new/backend')
from app import main_from_txt as m
logs=subprocess.check_output(['journalctl','-u','ad-member-new.service','--since','2026-10-23 00:03:00','--no-pager'],text=True)
for line in logs.splitlines():
 if 'GET /api/callbacks/taku/reward?' not in line: continue
 url=line.split('GET ',1)[1].split(' HTTP/',1)[0]
 q={k:v[0] for k,v in parse_qs(urlsplit(url).query).items()}
 print('CALLBACK_FIELDS',sorted(q))
 from app.taku_ecpm import _game_keys
 print('PROOF_SHAPE',json.dumps({k:{'length':len(q.get(k,'')),'spaces':q.get(k,'').count(' '),'placeholder':'{' in q.get(k,'') or '$' in q.get(k,'')} for k in ['e_c','e_c_cny','s_id']}))
 print('KEY_ID_KNOWN',q.get('s_id') in (_game_keys(238) or {}).get('keys',{}))
 try:
  proof=m.verify_ecpm(238,q.get('adsource_id',''),q.get('e_c',''),q.get('e_c_cny',''),q.get('s_id',''))
  print('SERVER_PROOF',bool(proof))
 except Exception as error: print('SERVER_PROOF_ERROR',type(error).__name__,type(error.__cause__).__name__)
with m.SessionLocal() as s:
 u=s.get(m.Member,695018)
 print('MEMBER',json.dumps({k:str(getattr(u,k)) for k in ['id','coin','freeze_coin','is_white','whitelist_min_coin','whitelist_max_coin']}))
 r=s.get(m.device_risk.DeviceRule,238)
 print('RISK_RULE',m.device_risk.rule_data(r))
 for r in s.execute(m.text("select name from sqlite_master where type='table' and (name like '%callback%' or name like '%request%')")):
  print('AUDIT_TABLE',r[0])
 for a in s.scalars(m.select(m.AppAdSession).where(m.AppAdSession.member_id==695018).order_by(m.AppAdSession.created_at.desc()).limit(3)):
  print('AD',json.dumps({k:str(getattr(a,k)) for k in ['id','status','created_at','impressed_at','completed_at','coin_log_id']}))
  for e in s.scalars(m.select(m.AppAdEvent).where(m.AppAdEvent.ad_session_id==a.id)):
   print('EVENT',e.event_type)
   if e.event_type=='client_metadata':
    data=json.loads(e.result_json);print('METADATA',json.dumps({k:data.get(k) for k in ['event','title','app_name','source_id','revenue_diagnostic']}))
  for f in s.scalars(m.select(m.AdFlowLog).where(m.AdFlowLog.ad_session_id==a.id)):
   print('FLOW',f.event_type,f.status,f.error_code)
  for l in s.scalars(m.select(m.member_policy.RewardLedger).where(m.member_policy.RewardLedger.ad_session_id==a.id)):
   print('LEDGER',l.kind,l.beneficiary_id,str(l.amount))
 for d in s.scalars(m.select(m.device_risk.DeviceCheck).where(m.device_risk.DeviceCheck.member_id==695018).order_by(m.device_risk.DeviceCheck.created_at.desc()).limit(2)):
  print('RISK',d.status,str(d.created_at),str(d.verified_at))
'''
try:
 sftp=client.open_sftp()
 with sftp.file('/tmp/ad-member-device-evidence.py','w') as f:f.write(code)
 _,out,err=client.exec_command('systemd-run --quiet --wait --pipe -p WorkingDirectory=/www/wwwroot/ad_member_new -p EnvironmentFile=/www/wwwroot/ad_member_new/.env /www/wwwroot/ad_member_new/.venv/bin/python /tmp/ad-member-device-evidence.py',timeout=30)
 print(out.read().decode());print(err.read().decode())
 _,out,err=client.exec_command("journalctl -u ad-member-new.service --since '2026-10-23 00:03:00' --no-pager | grep -E 'Traceback|Error|Exception|invalid TAKU|invalid ad session|Reward policy|callback' | tail -25",timeout=15)
 for line in out.read().decode().splitlines():
  if 'callback' in line:
   line=re.sub(r'([?]).*?( HTTP/)',r'?[REDACTED]\2',line)
   if len(line)>800:line=line[:100]+' [DETAIL REDACTED]'
  print(line)
finally:client.close()
