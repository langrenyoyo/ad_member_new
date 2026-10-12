"""Exercise admin level changes and the connected isolated APP; restore on exit."""
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time
import xml.etree.ElementTree as ET


def main():
    database = Path(sys.argv[1]).resolve(strict=True)
    if not database.parent.name.startswith('ad-member-device-') or database.name != 'device.db':
        raise SystemExit('Only a disposable device database is allowed')
    os.environ.update(DATABASE_URL='sqlite:///' + database.as_posix(), APP_ENV='development',
                      JWT_SECRET=secrets.token_urlsafe(48), PAYMENT_PROVIDER='', TAKU_SEC_KEY='')
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
    from app import main_from_txt as m
    from fastapi.testclient import TestClient
    from sqlalchemy import func, select

    def adb(*args):
        return subprocess.check_output(['adb', '-s', '47D0220908002529', *args])

    def nodes():
        adb('shell', 'uiautomator', 'dump', '/sdcard/device-level-test.xml')
        return [n for n in ET.fromstring(adb('shell', 'cat', '/sdcard/device-level-test.xml')).iter('node')
                if n.get('package') == 'com.heshangzhilian.yazhiyiji.devtest']

    def tap(label):
        node = next(n for n in nodes() if n.get('text') == label and n.get('bounds') != '[0,0][0,0]')
        x1, y1, x2, y2 = map(int, re.findall(r'\d+', node.get('bounds')))
        adb('shell', 'input', 'tap', str((x1+x2)//2), str((y1+y2)//2))

    with m.SessionLocal() as s:
        assert s.get(m.Game, 1).name == 'Device test'
        original = s.get(m.member_policy.Enrollment, 2).level
        before = (s.get(m.Member, 2).coin, s.scalar(select(func.count()).select_from(m.CoinLog)))
        auth = {'Authorization': 'Bearer ' + m.create_access_token(s.get(m.AdminUser, 1))}
    client = TestClient(m.app)  # No lifespan: never initialize another database.
    tap('分佣收益')
    try:
        for level, label in [(0, '用户'), (1, 'V1'), (2, 'V2'), (3, '代理')]:
            response = client.put('/api/v1/members/2/level', json={'level': level}, headers=auth)
            assert response.status_code == 200, response.status_code
            tap('刷新')
            time.sleep(.8)
            texts = [n.get('text', '') for n in nodes()]
            expected = f'等级：{label} · 直属邀请 1 人'
            assert expected in texts, [t for t in texts if t.startswith('等级')]
            assert any('累计佣金：2.000000' in t for t in texts), 'Historical earnings changed'
            print(json.dumps({'level': level, 'display': label, 'historical_earnings_unchanged': True}, ensure_ascii=False))
    finally:
        response = client.put('/api/v1/members/2/level', json={'level': original}, headers=auth)
        assert response.status_code == 200
        with m.SessionLocal() as s:
            after = (s.get(m.Member, 2).coin, s.scalar(select(func.count()).select_from(m.CoinLog)))
            assert before == after, 'Unexpected wallet mutation'
        tap('刷新')
        client.close()
        m.engine.dispose()
        print('Original level restored; wallet and coin logs unchanged')


if __name__ == '__main__':
    main()
