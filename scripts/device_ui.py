"""Small adb UI inspector for the isolated device-test app only."""
import argparse
import re
import subprocess
import xml.etree.ElementTree as ET

PACKAGE = 'com.heshangzhilian.yazhiyiji.devtest'


def adb(*args):
    return subprocess.check_output(['adb', *args])


def nodes():
    adb('shell', 'uiautomator', 'dump', '/sdcard/member-device-test.xml')
    root = ET.fromstring(adb('shell', 'cat', '/sdcard/member-device-test.xml'))
    return [n for n in root.iter('node') if n.get('package') == PACKAGE]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tap')
    args = parser.parse_args()
    current = nodes()
    if args.tap:
        matches = [n for n in current if args.tap in (n.get('text'), n.get('content-desc'))
                   and n.get('bounds') != '[0,0][0,0]']
        if len(matches) != 1:
            raise SystemExit(f'Expected one match, found {len(matches)}')
        x1, y1, x2, y2 = map(int, re.findall(r'\d+', matches[0].get('bounds')))
        adb('shell', 'input', 'tap', str((x1+x2)//2), str((y1+y2)//2))
    else:
        for n in current:
            if n.get('text') or n.get('content-desc') or n.get('class') == 'android.widget.EditText':
                label = '[password]' if n.get('password') == 'true' else n.get('text')
                print(label, n.get('content-desc'), n.get('bounds'), n.get('class'), 'enabled='+str(n.get('enabled')))


if __name__ == '__main__':
    main()
