"""Deploy the reviewed client-reward flow with backup and automatic rollback."""
from pathlib import Path
import base64
import datetime
import re

import paramiko


ROOT = Path(__file__).resolve().parents[1]
REMOTE_ROOT = "/www/wwwroot/ad_member_new"
FILES = ["backend/app/main_from_txt.py", "backend/app/member_policy.py"]


def credential(source: str, name: str) -> str:
    match = re.search(r"^" + name + r"\s*[:：]\s*(\S+)", source, re.M)
    if not match:
        raise RuntimeError(f"Missing server credential: {name}")
    return match.group(1)


def main() -> None:
    source = (ROOT / "serverdata.md").read_text(encoding="utf-8")
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = f"/www/backup/ad-member-client-reward-{stamp}"
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.connect(
        credential(source, "IP"),
        username=credential(source, "user"),
        password=credential(source, "password"),
        look_for_keys=False,
        allow_agent=False,
        timeout=10,
        auth_timeout=10,
    )

    def run(command: str, timeout: int = 120) -> str:
        _, stdout, stderr = client.exec_command(command, timeout=timeout)
        output = stdout.read().decode("utf-8", errors="replace")
        error = stderr.read().decode("utf-8", errors="replace")
        status = stdout.channel.recv_exit_status()
        if output.strip():
            print(output.strip())
        if status:
            if error.strip():
                print(error.strip())
            raise RuntimeError(f"Remote command failed with exit {status}")
        return output

    try:
        run("curl -fsS http://127.0.0.1:8001/api/health")
        run(f"mkdir -p {backup}/backend/app")
        for relative in FILES:
            run(f"cp -p {REMOTE_ROOT}/{relative} {backup}/{relative}")

        database_backup = f"""import pathlib, sqlite3, sys
sys.path.insert(0, {str(REMOTE_ROOT + '/backend')!r})
from app.main_from_txt import engine
if engine.url.get_backend_name() != 'sqlite':
    raise RuntimeError('Database-specific backup required')
target = pathlib.Path({str(backup + '/database.sqlite')!r})
with sqlite3.connect(engine.url.database) as source, sqlite3.connect(str(target)) as destination:
    source.backup(destination)
print('Database backup complete')
"""
        payload = base64.b64encode(database_backup.encode()).decode()
        prefix = (
            "systemd-run --quiet --wait --pipe "
            f"-p WorkingDirectory={REMOTE_ROOT} "
            f"-p EnvironmentFile={REMOTE_ROOT}/.env "
        )
        run(
            prefix
            + f"{REMOTE_ROOT}/.venv/bin/python -c \"import base64;"
            + f"exec(base64.b64decode('{payload}'))\""
        )

        sftp = client.open_sftp()
        for relative in FILES:
            sftp.put(str(ROOT / relative), f"{REMOTE_ROOT}/{relative}.pending")
        run(
            f"{REMOTE_ROOT}/.venv/bin/python -m py_compile "
            f"{REMOTE_ROOT}/backend/app/main_from_txt.py.pending "
            f"{REMOTE_ROOT}/backend/app/member_policy.py.pending"
        )

        run("systemctl stop ad-member-new.service")
        try:
            for relative in FILES:
                run(f"mv {REMOTE_ROOT}/{relative}.pending {REMOTE_ROOT}/{relative}")
            run("systemctl start ad-member-new.service")
            run(
                "curl --retry 12 --retry-connrefused --retry-delay 1 "
                "-fsS http://127.0.0.1:8001/api/health"
            )
        except Exception:
            run("systemctl stop ad-member-new.service")
            for relative in FILES:
                run(f"cp -p {backup}/{relative} {REMOTE_ROOT}/{relative}")
            run("systemctl start ad-member-new.service")
            run(
                "curl --retry 12 --retry-connrefused --retry-delay 1 "
                "-fsS http://127.0.0.1:8001/api/health"
            )
            raise

        run(
            "grep -n -E "
            "'client_reward_with_server_reconciliation|client_reward_granted|"
            "def settle\\(.*allow_fallback' "
            f"{REMOTE_ROOT}/backend/app/main_from_txt.py "
            f"{REMOTE_ROOT}/backend/app/member_policy.py"
        )
        run(
            "systemctl show ad-member-new.service "
            "-p ActiveState -p MainPID -p ActiveEnterTimestamp --no-pager"
        )
        print(f"Backup: {backup}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
