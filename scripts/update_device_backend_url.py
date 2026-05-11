#!/usr/bin/env python3
"""Point existing PaperDrop devices at the production backend.

Usage:
  PAPERDROP_SSH_PASSWORD=... python3 scripts/update_device_backend_url.py 192.168.1.43 192.168.1.126

The script tries a small set of known usernames, installs systemd environment
overrides for both current agent service names, and restarts the active service.
"""

import os
import sys
from typing import Iterable

import paramiko


BACKEND_WS_URL = os.environ.get(
    "PAPERDROP_WS_URL",
    "wss://api.paperdrop.me/api/device/connect",
)
USERS = [user.strip() for user in os.environ.get("PAPERDROP_SSH_USERS", "pi,paperdrop").split(",") if user.strip()]
PASSWORD = os.environ.get("PAPERDROP_SSH_PASSWORD")
SERVICES = ["paperdrop-ws-agent.service", "paperdrop.service"]


def run(ssh: paramiko.SSHClient, command: str) -> tuple[int, str, str]:
    stdin, stdout, stderr = ssh.exec_command(command, timeout=20)
    code = stdout.channel.recv_exit_status()
    return code, stdout.read().decode(errors="replace"), stderr.read().decode(errors="replace")


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def connect(ip: str) -> tuple[str, paramiko.SSHClient] | None:
    for user in USERS:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(ip, username=user, password=PASSWORD, timeout=8, banner_timeout=8, auth_timeout=8)
            return user, ssh
        except Exception:
            ssh.close()
    return None


def update_device(ip: str) -> bool:
    result = connect(ip)
    if not result:
        print(f"{ip}: unable to connect with configured users", file=sys.stderr)
        return False

    user, ssh = result
    print(f"{ip}: connected as {user}")

    env_line = f"Environment=PAPERDROP_WS_URL={BACKEND_WS_URL}"
    for service in SERVICES:
        override_dir = f"/etc/systemd/system/{service}.d"
        override_file = f"{override_dir}/10-paperdrop-backend.conf"
        command = (
            f"sudo mkdir -p {shell_quote(override_dir)} && "
            f"printf '%s\\n%s\\n' '[Service]' {shell_quote(env_line)} | sudo tee {shell_quote(override_file)} >/dev/null"
        )
        code, _, err = run(ssh, command)
        if code != 0:
            print(f"{ip}: failed writing override for {service}: {err.strip()}", file=sys.stderr)

    run(ssh, "sudo systemctl daemon-reload")

    restarted = False
    for service in SERVICES:
        code, out, _ = run(ssh, f"systemctl is-enabled {shell_quote(service)} 2>/dev/null || true")
        if out.strip() in {"enabled", "static", "generated"}:
            code, _, err = run(ssh, f"sudo systemctl restart {shell_quote(service)}")
            if code == 0:
                print(f"{ip}: restarted {service}")
                restarted = True
            else:
                print(f"{ip}: failed restarting {service}: {err.strip()}", file=sys.stderr)

    if not restarted:
        print(f"{ip}: no known PaperDrop service was enabled", file=sys.stderr)

    code, out, _ = run(
        ssh,
        "systemctl is-active paperdrop-ws-agent.service 2>/dev/null || "
        "systemctl is-active paperdrop.service 2>/dev/null || true",
    )
    print(f"{ip}: active status: {out.strip() or 'unknown'}")
    ssh.close()
    return restarted


def main(argv: Iterable[str]) -> int:
    ips = list(argv)
    if not PASSWORD:
        print("Set PAPERDROP_SSH_PASSWORD before running.", file=sys.stderr)
        return 2
    if not ips:
        print("Usage: PAPERDROP_SSH_PASSWORD=... python3 scripts/update_device_backend_url.py <ip> [ip...]", file=sys.stderr)
        return 2

    ok = True
    for ip in ips:
        ok = update_device(ip) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
