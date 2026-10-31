"""Back up and execute the isolated ad-list fixture on the configured server."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shlex
import paramiko

ROOT = Path(__file__).resolve().parents[1]
REMOTE = "/www/wwwroot/ad_member_new"
BATCH = "20261030-AD"
GAME_ID = 238
COUNT = 120
BACKUP = "/www/backup/ad-member-adlist-testdata-20261030"


def server_field(name):
    source = (ROOT / "serverdata.md").read_text(encoding="utf-8")
    for line in source.splitlines():
        if line.startswith(name + ":"):
            return line.split(":", 1)[1].strip()
    raise RuntimeError("Missing server connection field")


def main():
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.connect(server_field("IP"), username=server_field("user"),
                   password=server_field("password"), look_for_keys=False,
                   allow_agent=False, timeout=10, auth_timeout=10,
                   banner_timeout=10)

    def run(command, timeout=120):
        _, out, err = client.exec_command(command, timeout=timeout)
        stdout = out.read().decode("utf-8", errors="replace")
        stderr = err.read().decode("utf-8", errors="replace")
        code = out.channel.recv_exit_status()
        if code:
            raise RuntimeError(f"remote command failed ({code}): {stderr[-1200:]}")
        return stdout

    sftp = client.open_sftp()
    remote_seed = REMOTE + "/scripts/.seed_ad_list_preview_20261030.tmp.py"
    remote_backup = "/tmp/backup_ad_list_preview_20261030.py"
    sftp.put(str(ROOT / "scripts/seed_ad_list_preview.py"), remote_seed)
    backup_code = f'''import pathlib, sqlite3, sys
sys.path.insert(0, {REMOTE!r} + "/backend")
from app.main_from_txt import engine
target = pathlib.Path({BACKUP!r})
target.mkdir(parents=True, exist_ok=True)
if engine.url.get_backend_name() != "sqlite":
    raise RuntimeError("expected sqlite production database")
backup_file = target / "database-before.sqlite"
if backup_file.exists():
    raise RuntimeError("refusing to overwrite an existing database backup")
with sqlite3.connect(engine.url.database) as src, sqlite3.connect(str(backup_file)) as dst:
    src.backup(dst)
print(str(backup_file))
'''
    with sftp.file(remote_backup, "w") as handle:
        handle.write(backup_code)

    try:
        # A dry run validates the target game/member invariants and produces no writes.
        prefix = (f"systemd-run --quiet --wait --pipe -p WorkingDirectory={shlex.quote(REMOTE)} "
                  f"-p EnvironmentFile={shlex.quote(REMOTE + '/.env')} ")
        dry = run(prefix + f"{shlex.quote(REMOTE + '/.venv/bin/python')} {remote_seed} "
                  f"--batch {BATCH} --game-id {GAME_ID}")
        backup_result = run(prefix + f"{shlex.quote(REMOTE + '/.venv/bin/python')} {remote_backup}")
        committed = run(prefix + f"{shlex.quote(REMOTE + '/.venv/bin/python')} {remote_seed} "
                        f"--batch {BATCH} --game-id {GAME_ID} --commit")
        manifest = json.loads(committed)
        manifest["executed_at_utc"] = datetime.now(timezone.utc).isoformat()
        manifest["backup_dir"] = BACKUP
        with sftp.file(BACKUP + "/manifest.json", "w") as handle:
            handle.write(json.dumps(manifest, ensure_ascii=False, indent=2))

        # Read-only post-write check: count this batch, verify zero wallet movement,
        # and ensure the production process is still healthy.
        verify_code = f'''import json, sys
sys.path.insert(0, {REMOTE!r} + "/backend")
from app import main_from_txt as m
from sqlalchemy import func, select
with m.SessionLocal() as db:
    rows = db.scalars(select(m.AdRecord).where(m.AdRecord.game_id == {GAME_ID}, m.AdRecord.request_id.startswith("TEST-{BATCH}-"))).all()
    member_ids = [x.id for x in db.scalars(select(m.Member).where(m.Member.username.startswith("TEST-20261029-YZ-")).order_by(m.Member.id)).all()]
    print(json.dumps({{"count": len(rows), "coin_sum": str(db.scalar(select(func.coalesce(func.sum(m.Member.coin), 0)).where(m.Member.id.in_(member_ids)))), "freeze_coin_sum": str(db.scalar(select(func.coalesce(func.sum(m.Member.freeze_coin), 0)).where(m.Member.id.in_(member_ids)))), "coin_logs": db.scalar(select(func.count(m.CoinLog.id)).where(m.CoinLog.user_id.in_(member_ids)))}}))
'''
        verify_path = "/tmp/verify_ad_list_preview_20261030.py"
        with sftp.file(verify_path, "w") as handle:
            handle.write(verify_code)
        verify = run(prefix + f"{shlex.quote(REMOTE + '/.venv/bin/python')} {verify_path}")
        health = run("systemctl is-active ad-member-new.service && curl --retry 3 --retry-connrefused --retry-delay 1 -fsS http://127.0.0.1:8001/api/health")
        api_check_code = f'''import json, os, sys
sys.path.insert(0, {REMOTE!r} + "/backend")
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from app import main_from_txt as m
with m.SessionLocal() as db:
    admin = db.scalar(m.select(m.AdminUser).where(m.AdminUser.status == 1))
    if admin is None:
        raise RuntimeError("no active admin")
    token = m.create_access_token(admin)
url = "http://127.0.0.1:8001/api/v1/ads?" + urlencode({{"q":"TEST-{BATCH}-REQ-", "game_id":{GAME_ID}, "limit":200}})
request = Request(url, headers={{"Authorization":"Bearer "+token}})
with urlopen(request, timeout=15) as response:
    data = json.loads(response.read())
items = data.get("items", data.get("data", {{}}).get("items", []))
total = data.get("total", data.get("data", {{}}).get("total"))
if response.status != 200 or total != {COUNT} or len(items) != {COUNT}:
    raise RuntimeError("ad list API did not return the complete fixture batch")
print(json.dumps({{"http_status":response.status, "total":total, "matching":len(items), "sample_request_id":items[0].get("request_id") if items else None}}))
'''
        api_check_path = "/tmp/check_ad_list_preview_api_20261030.py"
        with sftp.file(api_check_path, "w") as handle:
            handle.write(api_check_code)
        api_check = run(prefix + f"{shlex.quote(REMOTE + '/.venv/bin/python')} {api_check_path}")
        print(json.dumps({"dry_run": json.loads(dry), "backup": backup_result.strip(), "manifest": manifest,
                          "verify": json.loads(verify), "api_check": json.loads(api_check),
                          "health": health.strip()}, ensure_ascii=False, indent=2))
    finally:
        try:
            run("rm -f " + " ".join(shlex.quote(p) for p in
                (remote_seed, remote_backup, "/tmp/verify_ad_list_preview_20261030.py",
                 "/tmp/check_ad_list_preview_api_20261030.py")))
        except Exception:
            pass
        sftp.close()
        client.close()


if __name__ == "__main__":
    main()
