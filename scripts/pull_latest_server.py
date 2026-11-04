"""Back up a dirty server worktree, fast-forward it, and restart the service."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shlex
import paramiko

ROOT = Path(__file__).resolve().parents[1]
REMOTE = "/www/wwwroot/ad_member_new"
EXPECTED = "ef742232aff6f51a063a4b7a442d57dc7fa964ac"


def credentials():
    result = {}
    for line in (ROOT / "serverdata.md").read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip() in {"IP", "user", "password"}:
            result[key.strip()] = value.strip()
    return result


def main():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = f"/www/backup/ad-member-update-{stamp}"
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    c = credentials()
    client.connect(c["IP"], username=c["user"], password=c["password"],
                   look_for_keys=False, allow_agent=False, timeout=10,
                   auth_timeout=10)

    def run(command, timeout=120):
        _, out, err = client.exec_command(command, timeout=timeout)
        stdout = out.read().decode("utf-8", errors="replace")
        stderr = err.read().decode("utf-8", errors="replace")
        code = out.channel.recv_exit_status()
        if stdout.strip():
            print(stdout.strip())
        if code:
            if stderr.strip():
                print(stderr.strip())
            raise RuntimeError(f"remote command failed ({code})")
        return stdout

    sftp = client.open_sftp()
    backup_script = f'''import pathlib, sqlite3, shutil, subprocess, json, datetime
root = pathlib.Path({REMOTE!r})
backup = pathlib.Path({backup!r})
(backup / "worktree").mkdir(parents=True, exist_ok=True)
status = subprocess.check_output(["git", "-c", "safe.directory=" + str(root), "status", "--short"], cwd=root, text=True)
head = subprocess.check_output(["git", "-c", "safe.directory=" + str(root), "rev-parse", "HEAD"], cwd=root, text=True).strip()
with sqlite3.connect(str(root / "backend/app.db")) as src, sqlite3.connect(str(backup / "database-before.sqlite")) as dst:
    src.backup(dst)
files = ["backend/app/main_from_txt.py", "backend/app/main_from_txt.py.before-callback-20261022T171648Z", "scripts/seed_admin_preview.py", "scripts/seed_withdrawal_preview.py"]
for name in files:
    source = root / name
    if source.exists():
        target = backup / "worktree" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
manifest = {{"created_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "pre_update_head": head, "pre_update_status": status, "backed_up_files": files}}
(backup / "manifest-pre.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(manifest, ensure_ascii=False))
'''
    remote_backup = "/tmp/ad_member_update_backup.py"
    with sftp.file(remote_backup, "w") as handle:
        handle.write(backup_script)
    try:
        run(f"mkdir -p {shlex.quote(backup)}")
        run(f"{REMOTE}/.venv/bin/python {remote_backup}")
        run("systemctl stop ad-member-new.service", timeout=30)
        try:
            for source, target in (
                ("scripts/seed_admin_preview.py", "scripts/seed_admin_preview.py.old"),
                ("scripts/seed_withdrawal_preview.py", "scripts/seed_withdrawal_preview.py.old"),
                ("backend/app/main_from_txt.py.before-callback-20261022T171648Z", "main_from_txt.py.before-callback-20261022T171648Z"),
            ):
                run(f"mv {REMOTE}/{source} {backup}/worktree/{target}")
            run(f"cd {REMOTE} && git -c safe.directory={REMOTE} reset --hard HEAD && git -c safe.directory={REMOTE} pull --ff-only origin main")
            head = run(f"cd {REMOTE} && git -c safe.directory={REMOTE} rev-parse HEAD").strip()
            if head != EXPECTED:
                raise RuntimeError("Server did not reach the expected commit")
            run(f"cd {REMOTE} && {REMOTE}/.venv/bin/python -m py_compile backend/app/main_from_txt.py backend/app/member_policy.py backend/app/payouts.py backend/app/subsidy_campaigns.py", timeout=60)
        except Exception:
            run(f"cp -p {backup}/worktree/backend/app/main_from_txt.py {REMOTE}/backend/app/main_from_txt.py", timeout=30)
            raise
        finally:
            run("systemctl start ad-member-new.service", timeout=30)
        try:
            run("curl --retry 12 --retry-connrefused --retry-delay 1 -fsS http://127.0.0.1:8001/api/health", timeout=45)
        except Exception:
            run("systemctl stop ad-member-new.service", timeout=30)
            run(f"cp -p {backup}/worktree/backend/app/main_from_txt.py {REMOTE}/backend/app/main_from_txt.py", timeout=30)
            run("systemctl start ad-member-new.service", timeout=30)
            run("curl --retry 12 --retry-connrefused --retry-delay 1 -fsS http://127.0.0.1:8001/api/health", timeout=45)
            raise
        result = run(f"cd {REMOTE} && printf 'HEAD=' && git -c safe.directory={REMOTE} rev-parse --short HEAD && printf '\\nSTATUS=' && git -c safe.directory={REMOTE} status --short && printf 'SERVICE=' && systemctl is-active ad-member-new.service")
        post_script = f'''import pathlib, subprocess, json
root = pathlib.Path({REMOTE!r})
backup = pathlib.Path({backup!r})
head = subprocess.check_output(["git", "-c", "safe.directory=" + str(root), "rev-parse", "HEAD"], cwd=root, text=True).strip()
status = subprocess.check_output(["git", "-c", "safe.directory=" + str(root), "status", "--short"], cwd=root, text=True)
manifest = json.loads((backup / "manifest-pre.json").read_text(encoding="utf-8"))
manifest.update({{"post_update_head": head, "post_update_status": status, "expected_remote": {EXPECTED!r}, "health": "ok", "service": "active"}})
(backup / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(manifest, ensure_ascii=False))
'''
        remote_manifest = "/tmp/ad_member_update_manifest.py"
        with sftp.file(remote_manifest, "w") as handle:
            handle.write(post_script)
        run(f"{REMOTE}/.venv/bin/python {remote_manifest}")
        print("BACKUP_DIR=" + backup)
    finally:
        try:
            run(f"rm -f {remote_backup} /tmp/ad_member_update_manifest.py", timeout=20)
        except Exception:
            pass
        sftp.close()
        client.close()


if __name__ == "__main__":
    main()
