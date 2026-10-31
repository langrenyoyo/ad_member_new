"""Read-only verification of the 2026-10-30 ad-list fixture batch."""
import json
from pathlib import Path
import shlex
import paramiko

ROOT = Path(__file__).resolve().parents[1]
REMOTE = "/www/wwwroot/ad_member_new"
BACKUP = "/www/backup/ad-member-adlist-testdata-20261030"
BATCH = "20261030-AD"


def server_field(name):
    source = (ROOT / "serverdata.md").read_text(encoding="utf-8")
    for line in source.splitlines():
        if line.startswith(name + ":"):
            return line.split(":", 1)[1].strip()
    raise RuntimeError("Missing server connection field")


client = paramiko.SSHClient()
client.load_system_host_keys()
client.connect(server_field("IP"), username=server_field("user"),
               password=server_field("password"), look_for_keys=False,
               allow_agent=False, timeout=10, auth_timeout=10, banner_timeout=10)
sftp = client.open_sftp()
remote_check = REMOTE + "/scripts/.verify_ad_list_preview_20261030.tmp.py"
code = f'''import json, sys
sys.path.insert(0, {REMOTE!r} + "/backend")
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from app import main_from_txt as m
from sqlalchemy import func, select
with m.SessionLocal() as db:
    rows = db.scalars(select(m.AdRecord).where(m.AdRecord.game_id == 238,
        m.AdRecord.request_id.startswith("TEST-{BATCH}-REQ-"))).all()
    members = db.scalars(select(m.Member).where(m.Member.username.startswith("TEST-20261029-YZ-"))).all()
    coin_logs = db.scalar(select(func.count(m.CoinLog.id)).where(m.CoinLog.user_id.in_([x.id for x in members]))) if members else 0
    wallet = {{"coin": str(sum((x.coin or 0 for x in members), start=0)),
              "freeze_coin": str(sum((x.freeze_coin or 0 for x in members), start=0)),
              "coin_logs": coin_logs}}
    admin = db.scalar(select(m.AdminUser).where(m.AdminUser.status == 1))
    if admin is None: raise RuntimeError("no active admin")
    token = m.create_access_token(admin)
    counts = {{"total":len(rows), "success":sum(x.is_look == 1 for x in rows),
              "failed":sum(x.is_look == 0 for x in rows),
              "groups":{{"main":sum(x.ad_group == m.MAIN_AD_LABEL for x in rows), "secondary":sum(x.ad_group == m.SECONDARY_AD_LABEL for x in rows)}}}}
url = "http://127.0.0.1:8001/api/v1/ads?" + urlencode({{"q":"TEST-{BATCH}-REQ-", "game_id":238, "limit":200}})
request = Request(url, headers={{"Authorization":"Bearer "+token}})
with urlopen(request, timeout=15) as response:
    payload = json.loads(response.read())
items = payload.get("items", payload.get("data", {{}}).get("items", []))
total = payload.get("total", payload.get("data", {{}}).get("total"))
if len(rows) != 120 or total != 120 or len(items) != 120: raise RuntimeError("expected 120 API-visible records")
if any(float(wallet[k]) != 0 for k in ("coin", "freeze_coin")) or wallet["coin_logs"] != 0: raise RuntimeError("wallet changed unexpectedly")
print(json.dumps({{"db":counts,"api":{{"http_status":response.status,"total":total,"first_id":items[-1].get("id"),"last_id":items[0].get("id")}},"wallet":wallet}}))
'''

try:
    with sftp.file(remote_check, "w") as handle:
        handle.write(code)
    command = (f"systemd-run --quiet --wait --pipe -p WorkingDirectory={shlex.quote(REMOTE)} "
               f"-p EnvironmentFile={shlex.quote(REMOTE + '/.env')} "
               f"{shlex.quote(REMOTE + '/.venv/bin/python')} {shlex.quote(remote_check)}")
    _, out, err = client.exec_command(command, timeout=120)
    stdout = out.read().decode("utf-8", errors="replace")
    stderr = err.read().decode("utf-8", errors="replace")
    if out.channel.recv_exit_status():
        raise RuntimeError("read-only server verification failed: " + stderr[-1200:])
    backup_stat = sftp.stat(BACKUP + "/database-before.sqlite")
    with sftp.file(BACKUP + "/manifest.json", "r") as handle:
        manifest = json.loads(handle.read().decode("utf-8"))
    print(json.dumps({"verification": json.loads(stdout), "backup_bytes": backup_stat.st_size,
                      "manifest_batch": manifest["batch"],
                      "manifest_record_count": manifest["record_count"],
                      "manifest_id_range": [manifest["tables"]["ad_records"]["ids"][0],
                                            manifest["tables"]["ad_records"]["ids"][-1]],
                      "service": "active"}, ensure_ascii=False, indent=2))
finally:
    try:
        client.exec_command("rm -f " + shlex.quote(remote_check))[1].channel.recv_exit_status()
    except Exception:
        pass
    sftp.close()
    client.close()
