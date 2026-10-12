"""Restore a completed fixture's pending request to test recovery on a debug device.

Only accepts a disposable device-test database and the isolated devtest package.
No credentials are printed or written to local files.
"""
import argparse
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import xml.etree.ElementTree as ET

PACKAGE = 'com.heshangzhilian.yazhiyiji.devtest'
PREFS = 'shared_prefs/idiom_quiz_auth.xml'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('database', type=Path)
    parser.add_argument('--restore-pending', action='store_true')
    args = parser.parse_args()
    database = args.database.resolve(strict=True)
    assert database.parent.parent == Path(tempfile.gettempdir()).resolve()
    assert database.parent.name.startswith('ad-member-device-') and database.name == 'device.db'
    if args.restore_pending:
        subprocess.run(['adb', 'shell', 'am', 'force-stop', PACKAGE], check=True)
    raw = subprocess.check_output(['adb', 'exec-out', 'run-as', PACKAGE, 'cat', PREFS])
    root = ET.fromstring(raw)
    member_id = int(next(n.text for n in root if n.get('name') == 'user_id'))
    with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as session:
        assert session.execute('SELECT name FROM games WHERE id=1').fetchone()[0] == 'Device test'
        rows = session.execute('SELECT campaign_id, request_json FROM subsidy_reservations WHERE member_id=?', (member_id,)).fetchall()
        assert len(rows) == 1, 'Expected one existing fixture application'
        print('Member reservations:', len(rows))
        print('Member applications:', session.execute('SELECT COUNT(*) FROM subsidies WHERE user_id=?', (member_id,)).fetchone()[0])
    if args.restore_pending:
        for node in list(root):
            if node.get('name') == 'pending_campaign': root.remove(node)
        campaign, body = rows[0]
        ET.SubElement(root, 'string', name='pending_campaign').text = json.dumps({
            'path': f'subsidy-campaigns/{campaign}/applications', 'body': json.loads(body)})
        subprocess.run(['adb', 'shell', 'run-as', PACKAGE, 'tee', PREFS],
            input=ET.tostring(root, encoding='utf-8', xml_declaration=True),
            stdout=subprocess.DEVNULL, check=True)
        print('Pending fixture restored; start app to exercise recovery.')
    else:
        print('Pending remains:', any(n.get('name') == 'pending_campaign' for n in root))


if __name__ == '__main__':
    main()
