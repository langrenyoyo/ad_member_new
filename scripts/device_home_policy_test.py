"""Check isolated home-page policy refresh without restarting the APP."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import xml.etree.ElementTree as ET


def main():
    path = Path(sys.argv[1]).resolve(strict=True)
    assert path.parent.name.startswith('ad-member-device-') and path.name == 'device.db'
    os.environ.update(DATABASE_URL='sqlite:///' + path.as_posix(), APP_ENV='development',
                      JWT_SECRET=secrets.token_urlsafe(48), PAYMENT_PROVIDER='', TAKU_SEC_KEY='')
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
    from app import main_from_txt as m
    from fastapi.testclient import TestClient
    client = TestClient(m.app)

    def adb(*args):
        return subprocess.check_output(['adb', '-s', '47D0220908002529', *args])

    def texts():
        adb('shell', 'uiautomator', 'dump', '/sdcard/home-policy-test.xml')
        root = ET.fromstring(adb('shell', 'cat', '/sdcard/home-policy-test.xml'))
        return [n.get('text', '') for n in root.iter('node')
                if n.get('package') == 'com.heshangzhilian.yazhiyiji.devtest']

    def resume():
        adb('shell', 'input', 'keyevent', '3')
        adb('shell', 'am', 'start', '-n',
            'com.heshangzhilian.yazhiyiji.devtest/com.example.idiomquiz.MainActivity')
        time.sleep(1)
        return texts()

    with m.SessionLocal() as s:
        assert s.get(m.Game, 1).name == 'Device test'
        original_level = s.get(m.member_policy.Enrollment, 2).level
        original_policy = m.member_policy.policy(s, 1).model_dump(mode='json')
        auth = {'Authorization': 'Bearer ' + m.create_access_token(s.get(m.AdminUser, 1))}
    assert any(t.startswith('我的邀请码：') for t in texts()), 'Start on home with invite code visible'
    try:
        assert client.put('/api/v1/members/2/level', json={'level': 0}, headers=auth).status_code == 200
        changed = {**original_policy, 'announcement': 'Device announcement refresh verified',
                   'announcement_version': original_policy['announcement_version'] + 1}
        assert client.put('/api/v1/games/1/member-policy', json=changed, headers=auth).status_code == 200
        current = resume()
        assert changed['announcement'] in current, 'New announcement absent'
        assert not any(t.startswith('我的邀请码：') for t in current), 'Ineligible invite code remains visible'
        print('Demotion hides invite code; announcement refreshes on resume')
    finally:
        assert client.put('/api/v1/members/2/level', json={'level': original_level}, headers=auth).status_code == 200
        assert client.put('/api/v1/games/1/member-policy', json=original_policy, headers=auth).status_code == 200
        current = resume()
        assert any(t.startswith('我的邀请码：') for t in current)
        assert original_policy['announcement'] in current
        client.close()
        m.engine.dispose()
        print('Original level and announcement restored and visible')


if __name__ == '__main__':
    main()
