"""Append isolated, labelled admin preview data; never replace existing rows.

Run with the deployment environment: python scripts/seed_admin_preview.py --batch YYYYMMDD
The printed manifest lists exact IDs for later review/cleanup. Reusing a batch is rejected.
"""
import argparse
from datetime import timedelta
from decimal import Decimal
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app import main_from_txt as m
from sqlalchemy import select


def seed(batch, game_id=None):
    if not re.fullmatch(r'[A-Za-z0-9-]{1,20}', batch):
        raise ValueError('Batch must contain 1-20 letters, digits or hyphens')
    prefix = 'TEST-' + batch
    current = m.now()
    today = (current + timedelta(hours=8)).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(hours=8)
    manifest = {'batch': prefix, 'synthetic': True, 'tables': {}}
    with m.SessionLocal() as db:
        if db.scalar(select(m.Game.id).where(m.Game.game_key == prefix)) or db.scalar(select(m.Member.id).where(m.Member.username.startswith(prefix + '-'))):
            raise RuntimeError('Batch already exists; no data changed')
        def add(row):
            db.add(row)
            db.flush()
            table = row.__table__
            key = list(table.primary_key.columns)[0].name
            entry = manifest['tables'].setdefault(table.name, {'primary_key': key, 'ids': []})
            entry['ids'].append(getattr(row, key))
            return row

        if game_id is None:
            agent = add(m.Agent(name=f'测试数据-{batch}-主体', user_name=prefix, status=0, game_ad_status=0))
            game = add(m.Game(agent_id=agent.id, name=f'测试数据-{batch}-应用', game_key=prefix,
                status=0, ad_status=0, game_ad_status=0, commission_status=0,
                settings_json=json.dumps({'synthetic_batch': prefix})))
            add(m.GameTakuConfig(game_id=game.id, enabled=0, sec_key=''))
        else:
            game = db.get(m.Game, game_id)
            if game is None: raise RuntimeError('Target game does not exist')
            agent = db.get(m.Agent, game.agent_id)
            if agent is None: raise RuntimeError('Target agent does not exist')
        members = []
        for i in range(30):
            stamp = today + (current - today) * ((i + 1) / 31) if i < 15 else current - timedelta(days=1 + i % 6)
            parent = members[(i - 1) // 10].id if i >= 3 else 0
            level = 3 if i == 0 else 1 if i in (1, 2) else 0
            member = add(m.Member(agent_id=agent.id, game_id=game.id, parent_id=parent,
                username=f'{prefix}-{i+1:03}', name=f'{prefix}-测试会员{i+1:03}', is_true=1,
                status=0 if game_id is not None or i % 5 == 0 else 1, exchange_enable=0, vip=level,
                is_white=int(i % 5 == 1), whitelist_min_coin=Decimal('0.000010') if i % 5 == 1 else None,
                whitelist_max_coin=Decimal('0.000050') if i % 5 == 1 else None,
                device_id=f'{prefix}-device-{i:03}', ip=f'192.0.2.{i+1}',
                last_login_ip=f'192.0.2.{i+1}', last_login_time=current.isoformat(),
                last_login_device_id=f'{prefix}-device-{i:03}', created_at=stamp))
            members.append(member)
            add(m.member_policy.Enrollment(member_id=member.id, invite_code=f'{prefix}-{i:03}', parent_id=parent, level=level))
            add(m.MemberDevice(user_id=member.id, device_id=member.device_id,
                model=['TEST-Huawei', 'TEST-Xiaomi', 'TEST-OPPO'][i % 3], android_version=str(12+i % 3),
                app_version='test-preview', ip_address=member.ip, sim_info='TEST', risk_flag=i % 2,
                usb_debugging=int(i % 3 == 0), rooted=int(i % 7 == 0), device_id_ban=int(i % 9 == 0),
                total_clicks=10+i, today_clicks=i % 6, today_failed=i % 3, counter_date=(current+timedelta(hours=8)).date()))
            risk_device = add(m.device_risk.RiskDevice(game_id=game.id, device_key=m._token_hash(member.device_id),
                tags=json.dumps(['TEST_SYNTHETIC', 'TEST_RESET'] if i % 3 == 0 else ['TEST_SYNTHETIC']),
                reason=f'{prefix} 模拟设备风险，仅供页面测试', last_member_id=member.id,
                risk_until=current+timedelta(days=7) if i % 3 == 0 else None,
                override=['auto', 'allow', 'restrict'][i % 3], last_checked_at=current))
            add(m.device_risk.DeviceCheck(id=f'{prefix}-check-{i:03}', member_id=member.id, game_id=game.id,
                install_hash=m._token_hash(member.device_id), device_id=risk_device.id,
                expires_at=current-timedelta(seconds=1), status='test_preview', provider_request_id=prefix))
            for j in range(3):
                add(m.MemberLoginLog(user_id=member.id, game_id=game.id, device_id=member.device_id,
                    ip=member.ip, created_at=current-timedelta(hours=j)))
            add(m.MemberAppUsage(user_id=member.id, game_id=game.id, app_name='测试应用（模拟）',
                package_name='example.test.preview', count=i % 8+1, duration_seconds=60*(i+1),
                first_used_at=current-timedelta(days=2), last_used_at=current))
        for i in range(180):
            member = members[i % 30]
            stamp = today + (current-today)*((i+1)/121) if i < 120 else current-timedelta(days=1+i % 6, minutes=i)
            secondary = i % 3 == 0
            failed = i % 10 == 0
            ecpm = float(Decimal(20+i % 100))
            add(m.AdRecord(user_id=member.id, user_account=member.username, parent_id=member.parent_id,
                agent_id=agent.id, game_id=game.id, game_name=game.name, receive_name=member.name,
                ecpm=ecpm, coin=0, estimate_income=0, ad_network_platform_name='TEST-TAKU',
                ad_type='插屏' if secondary else '激励', ad_group='副广' if secondary else '主广',
                sub_ad_type='插屏' if secondary else '', is_fu=int(secondary), fu_type=3, is_rw=0,
                reward_type='测试未发奖', status='测试失败' if failed else '测试展示', watched_at=stamp,
                ad_code=f'{prefix}-placement', request_id=f'{prefix}-req-{i:03}', trans_id=f'{prefix}-trans-{i:03}',
                client_ecpm=None if failed else ecpm, callback_ecpm=None if i % 4 == 0 else ecpm*0.9,
                settlement_ecpm=None, callback_price_currency='' if i % 4 == 0 else 'CNY',
                attention_count=i % 4, gps_ip_cross_region=int(i % 8 == 0),
                risk_tags_json=json.dumps([{'code':'test_preview', 'label':'模拟测试数据', 'level':'info'}],ensure_ascii=False),
                created_at=stamp))
        for i in range(60):
            member = members[i % 30]
            index = i % 4
            add(m.RiskRecord(user_id=member.id, agent_id=agent.id, game_id=game.id,
                tagcode=f'{prefix}-'+['NORMAL','RESET','ROOT','IP'][index],
                tags=['测试-正常设备','测试-疑似双清','测试-Root设备','测试-IP异常'][index],
                hardware_main_id=member.device_id, ip=member.ip, action=['测试放行','测试观察','测试拦截','测试复核'][index],
                risk_score=[5,45,85,65][index], risk_level=['低','中','高','高'][index], network_status=i % 2,
                created_at=today+(current-today)*((i+1)/41) if i < 40 else current-timedelta(days=1+i % 6)))
        admin = db.scalar(select(m.AdminUser).where(m.AdminUser.role=='superadmin'))
        if admin:
            add(m.AdminOperation(admin_id=admin.id, title=f'创建测试数据 {prefix}', path='maintenance/seed-admin-preview', ip='127.0.0.1'))
        manifest.update(agent_id=agent.id, game_id=game.id, member_count=30, ad_count=180, risk_count=60, whitelist_count=6)
        db.commit()
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch', required=True)
    parser.add_argument('--game-id', type=int)
    args = parser.parse_args()
    print(json.dumps(seed(args.batch, args.game_id), ensure_ascii=False, indent=2))
