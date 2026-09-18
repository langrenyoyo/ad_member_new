"""Create deterministic preview data for every list page.

Safe to run repeatedly: rows tagged ``DEMO`` are replaced on each run.
"""
from datetime import datetime, timedelta
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from backend.app.main_from_txt import (SessionLocal, Agent, Game, Member, AdRecord,
    Withdrawal, Subsidy, CoinLog, DailyActivity, MemberLoginLog)

def seed():
    now=datetime.utcnow()
    with SessionLocal() as db:
        # Remove only this script's rows, preserving user data.
        for model, field in [(Agent,Agent.name),(Game,Game.name),(Member,Member.username),
                             (AdRecord,AdRecord.user_account),(Withdrawal,Withdrawal.good_name),
                             (Subsidy,Subsidy.receive_name),(CoinLog,CoinLog.remark)]:
            db.query(model).filter(field.like('DEMO%')).delete(synchronize_session=False)
        db.flush()
        agents=[Agent(name=f'DEMO Agent {i}',user_name=f'demo_agent_{i}',status=1,game_ad_status=i%2) for i in range(1,4)]
        db.add_all(agents); db.flush()
        games=[Game(agent_id=agents[i%3].id,name=f'DEMO Game {i+1}',game_key=f'demo-game-{i+1}',game_url='https://example.com/game',status=1,ad_status=1,game_type=i%3) for i in range(6)]
        db.add_all(games); db.flush()
        members=[Member(agent_id=agents[i%3].id,game_id=games[i%6].id,parent_id=0,username=f'DEMO User {i:03d}',name=f'DEMO User {i:03d}',ip=f'192.0.2.{i+1}',device_id=f'DEMO-device-{i:03d}',coin=100+i*10,vip=i%4,status=1,last_login_ip=f'192.0.2.{i+1}',last_login_time=(now-timedelta(hours=i)).isoformat()) for i in range(24)]
        db.add_all(members); db.flush()
        ads=[AdRecord(parent_id=1,parent_payment_name='DEMO Parent',user_id=members[i%24].id,user_account=members[i%24].username,agent_id=agents[i%3].id,game_id=games[i%6].id,game_name=games[i%6].name,receive_name='DEMO鐢ㄦ埛',ecpm=1.5+i%8,coin=10+i,estimate_income=.1*i,ad_network_platform_name='DEMO Platform',is_lottery=i%2,is_rw=1,reward_type='棰嗗彇',ad_type='incentive',ad_group='涓诲箍',is_type=i%2,is_fu=i%3==0,fu_type=1,is_look=1,status='鎴愬姛' if i%4 else '澶辫触',watched_at=now-timedelta(hours=i),ad_code=f'DEMO-CODE-{i:03d}',request_id=f'DEMO-REQ-{i:03d}',trans_id=f'DEMO-TRANS-{i:03d}') for i in range(40)]
        db.add_all(ads)
        db.add_all([Withdrawal(user_id=members[i].id,agent_id=agents[i%3].id,game_id=games[i%6].id,good_name=f'DEMO鎻愮幇{i:03d}',receive_name=f'DEMO User {i:03d}',receive_tel='18532306918',exchange_value=10+i,status=i%3) for i in range(12)])
        db.add_all([Subsidy(user_id=members[i].id,agent_id=agents[i%3].id,game_id=games[i%6].id,tx_price=20+i,price=18+i,receive_name=f'DEMO User {i:03d}',receive_tel='18532306918',status=i%3) for i in range(12)])
        db.add_all([CoinLog(user_id=members[i%24].id,agent_id=agents[i%3].id,game_id=games[i%6].id,coin_before=100+i,coin=10+i,coin_after=110+2*i,type=100+i%4,remark=f'DEMO Log {i:03d}') for i in range(30)])
        db.add_all([DailyActivity(game_id=games[i%6].id,date=(now-timedelta(days=i)).date(),num=10+i) for i in range(14)])
        db.add_all([MemberLoginLog(user_id=members[i%24].id,game_id=games[i%6].id,device_id=f'DEMO-device-{i:03d}',ip=f'192.0.2.{i+1}') for i in range(20)])
        db.commit(); print('seeded demo agents=3 games=6 members=24 ads=40 withdrawals=12 subsidies=12 coin_logs=30')
if __name__=='__main__': seed()



