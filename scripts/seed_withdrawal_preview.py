"""Append labelled withdrawal UI fixtures to an existing disabled test application."""
import argparse
from datetime import datetime, UTC, timedelta
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app import main_from_txt as m
from sqlalchemy import select


def seed(batch='20261028', game_id=None):
    prefix = 'TEST-' + batch
    if len(prefix) > 28 or not all(c.isalnum() or c == '-' for c in prefix):
        raise ValueError('Invalid batch')
    marker = prefix + '-WITHDRAW'
    current = m.now()
    today = (current + timedelta(hours=8)).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(hours=8)
    states = [(0,'pending_review','待审核'), (1,'pending_review','审核通过待打款'),
              (1,'queued','排队中'), (1,'processing','结果待确认'),
              (1,'succeeded','模拟到账'), (1,'failed','模拟失败'), (2,'rejected','已驳回')]
    manifest = {'batch': marker, 'synthetic': True, 'withdrawal_ids': [], 'payout_ids': [], 'states': {}}
    with m.SessionLocal() as db:
        game = db.get(m.Game, game_id) if game_id is not None else db.scalar(select(m.Game).where(m.Game.game_key == prefix))
        if game is None or (game_id is None and (game.status != 0 or game.ad_status != 0)):
            raise RuntimeError('Expected an existing disabled preview game')
        if db.scalar(select(m.Withdrawal.id).where(m.Withdrawal.good_name.startswith(marker))):
            raise RuntimeError('Batch exists; no changes made')
        members = db.scalars(select(m.Member).where(m.Member.game_id == game.id,
            m.Member.username.startswith(prefix + '-')).order_by(m.Member.id)).all()
        if len(members) < 28 or any(x.exchange_enable or x.is_true != 1 or not x.username.startswith(prefix) for x in members):
            raise RuntimeError('Expected internal test members with withdrawals disabled')
        for i in range(28):
            status, state, label = states[i % len(states)]
            member = members[i]
            cents = [100,500,1000,2000][i // 7]
            stamp = today + (current - today)*((i+1)/22) if i < 21 else current-timedelta(days=2, minutes=i)
            note = f'{marker} 测试数据：{label}，仅供页面演示，未冻结金币、未实际支付'
            withdrawal = m.Withdrawal(user_id=member.id, agent_id=game.agent_id, game_id=game.id,
                good_name=f'{marker}-{i+1:03} {label}', receive_name=f'测试收款人{i+1:03}',
                receive_tel=f'preview-{i+1}@example.invalid', exchange_value=cents/100,
                exchange_type=1, status=status, plan_status=1 if state=='succeeded' else 2 if state in ('queued','processing') else 0,
                device_manufacturer=['TEST-Huawei','TEST-Xiaomi','TEST-OPPO'][i%3],
                check_status_txt='模拟测试，非真实核检', remark=note, sub_msg=note,
                reason='测试驳回：模拟资料不完整' if state=='rejected' else '',
                audit_operator_name='测试审核员' if status else '', audited_at=stamp if status else None,
                transfer_operator_name='测试操作员' if state not in ('pending_review','rejected') else '',
                transferred_at=stamp if state=='succeeded' else None, created_at=stamp)
            db.add(withdrawal);db.flush()
            payout = m.payouts.Payout(withdrawal_id=withdrawal.id, member_id=member.id, game_id=game.id,
                request_key=f'{marker}-{i+1:03}', out_biz_no=f'{marker}-{i+1:03}',
                amount_cents=cents, coin_cost=0, account=withdrawal.receive_tel, real_name=withdrawal.receive_name,
                provider_scope='TEST_PREVIEW_NO_PAYMENT', state=state,
                provider_order_id=f'TEST-NOT-PAID-{i+1:03}' if state=='succeeded' else '',
                error=note, next_query_at=datetime(2099,1,1,tzinfo=UTC), created_at=stamp)
            db.add(payout);db.flush()
            manifest['withdrawal_ids'].append(withdrawal.id)
            manifest['payout_ids'].append(payout.id)
            manifest['states'][label] = manifest['states'].get(label,0)+1
        admin = db.scalar(select(m.AdminUser).where(m.AdminUser.role=='superadmin'))
        if admin:
            audit=m.AdminOperation(admin_id=admin.id, title=f'创建提现测试数据 {marker}', path='maintenance/seed-withdrawal-preview', ip='127.0.0.1')
            db.add(audit);db.flush();manifest['admin_operation_id']=audit.id
        manifest['game_id']=game.id
        db.commit()
    return manifest


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--batch',required=True)
    parser.add_argument('--game-id',type=int)
    args = parser.parse_args()
    print(json.dumps(seed(args.batch,args.game_id),ensure_ascii=False,indent=2))
