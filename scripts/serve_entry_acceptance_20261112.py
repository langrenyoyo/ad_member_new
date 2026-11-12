"""Loopback-only disposable fixture. No live SMS, ad rewards or production database."""
import json
import os
import sys
from datetime import timedelta
from pathlib import Path

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/app-entry-20261112'
out.mkdir(exist_ok=True, parents=True)
database = out / 'acceptance.sqlite'
if database.exists():
    raise SystemExit('Fixture already exists; use its existing server or explicitly archive it first.')
os.environ['DATABASE_URL'] = 'sqlite:///' + database.as_posix()
os.environ['APP_ENV'] = 'development'
os.environ['APP_DOWNLOAD_URL'] = '/downloads/yazhiyiji-latest.apk'
sys.path.insert(0, str(root / 'backend'))
from app import main_from_txt as m, member_policy as p, sms_auth as sms
import uvicorn

m.Base.metadata.create_all(m.engine)
with m.SessionLocal() as session:
    session.add(m.Agent(id=1, name='本地验收', status=1))
    session.add(m.Game(id=1, agent_id=1, name='鸭只易记（本地验收）', status=1, settings_json=json.dumps({
        'member_policy': {'require_registration_invite': True, 'require_invite': False, 'require_usage': False,
            'announcement': '欢迎使用鸭只易记。\n本公告用于本地隔离验收，请点击右上角 × 后进入主页面。',
            'announcement_version': 20261112}}, ensure_ascii=False)))
    for uid, phone in [(1, '13900001111'), (2, '13900002222')]:
        member = m.Member(id=uid, username=phone, name='本地验收会员', game_id=1, agent_id=1, status=1, coin=25)
        session.add(member)
        session.flush()
        row = p.enrollment(session, member)
        row.invite_code = 'A1B2C3' if uid == 2 else 'D4E5F6'
        row.level = 1 if uid == 2 else 0
    for i in range(25):
        log = m.CoinLog(user_id=1, game_id=1, coin=1)
        session.add(log); session.flush()
        session.add(m.AppAdSession(id='fixture-reward-'+str(i), member_id=1, game_id=1, agent_id=1,
            placement='rewarded', ad_type='rewarded', provider='taku', status='rewarded',
            request_id='req-fixture-'+str(i), session_token_hash='fixture',
            coin_log_id=log.id, impressed_at=m.now()-timedelta(minutes=i), completed_at=m.now()-timedelta(minutes=i),
            expires_at=m.now()+timedelta(minutes=5)))
    for i in range(10):
        session.add(m.AppAdSession(id='fixture-secondary-'+str(i), member_id=1, game_id=1, agent_id=1,
            placement='banner', ad_type='banner', provider='taku_secondary', status='impressed',
            request_id='secondary-fixture-'+str(i), session_token_hash='fixture', impressed_at=m.now(),
            expires_at=m.now()+timedelta(minutes=5)))
    session.commit()

# Verification remains enforced by the real API. Only the outbound provider and
# the test-only generated code are replaced in this dedicated process.
sms.send_sms = lambda phone, code: None
sms.secrets.randbelow = lambda upper: 123456 % upper
uvicorn.run(m.app, host='127.0.0.1', port=18080, lifespan='off', access_log=False)
