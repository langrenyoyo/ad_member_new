"""Read-only deployment inspection; credentials never enter command arguments."""
from pathlib import Path
import re
import paramiko

source = (Path(__file__).resolve().parents[1] / 'serverdata.md').read_text(encoding='utf-8')
def field(name):
    match = re.search(r'^'+name+r'\s*[:：]\s*(\S+)', source, re.M)
    if not match:
        raise RuntimeError('Missing connection field: '+name)
    return match.group(1)

client = paramiko.SSHClient()
client.load_system_host_keys()
try:
    client.connect(field('IP'), username=field('user'), password=field('password'),
        look_for_keys=False, allow_agent=False, timeout=10, auth_timeout=10, banner_timeout=10)
    _, stdout, stderr = client.exec_command(
        'cd /www/wwwroot/ad_member_new && git -c safe.directory=/www/wwwroot/ad_member_new status --short && git -c safe.directory=/www/wwwroot/ad_member_new rev-parse --short HEAD && '
        'systemctl list-timers --all --no-pager "taku-report-sync@*"; '
        'systemctl list-units --type=service --all --no-pager | grep -E "ad.member|uvicorn"; '
        'journalctl -u taku-report-sync@238.service -n 18 --no-pager; '
        'systemctl show ad-member-new.service -p WorkingDirectory -p ExecStart -p EnvironmentFiles; '
        'systemctl show taku-report-sync@238.service -p WorkingDirectory -p ExecStart -p EnvironmentFiles', timeout=20)
    print(stdout.read().decode('utf-8', errors='replace'))
    print(stderr.read().decode('utf-8', errors='replace'))
except Exception as error:
    print('Server inspection failed: '+type(error).__name__)
    raise SystemExit(1)
finally:
    client.close()
