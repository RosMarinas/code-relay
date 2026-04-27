#!/usr/bin/env python3
"""
remote_run.py — Forward commands to a remote server via SSH.

    python remote_run.py python train.py --batch_size 32
    python remote_run.py pytest tests/
    python remote_run.py --raw-env pip install torch
    python remote_run.py ls
"""

import sys
import subprocess
import shlex
import argparse
import re

# ============================================================
# CONFIGURATION — Modify these before use
# ============================================================
SERVER = ""                      # SSH user@host
REMOTE_DIR = ""                  # Remote project root

# Environment variables prepended to 'uv run' for python/pytest/pip
ADD_PYTHONPATH = True            # PYTHONPATH=.
ADD_HF_MIRROR = True             # HF_ENDPOINT (mirror for HuggingFace)
HF_MIRROR_URL = "https://hf-mirror.com"

# ---- Security: commands that trigger a confirmation prompt ----
CONFIRM_COMMANDS = [
    "rm",   "sudo",  "chmod",  "chown",   "chgrp",
    "mkfs", "dd",    "mkswap", "swapon",  "swapoff",
    "shutdown", "reboot", "halt", "poweroff", "init",
    "kill", "pkill", "killall",
    "mount", "umount",
    "passwd", "chroot", "visudo",
    "iptables", "ufw", "firewall-cmd",
    "scp", "rsync", "nc", "netcat", "ncat",
    "systemctl", "service",
    "useradd", "usermod", "userdel", "groupadd",
    "crontab", "at",
    "docker", "podman",
    "su", "newgrp",
]

# ---- Security: patterns that are ALWAYS blocked (no confirmation) ----
HARD_BLOCKED_PATTERNS = [
    "rm -rf /",
    "mkfs.",
    "> /dev/sd",
    "dd if=/dev/",
    ":(){ :|:& };:",
]

# ---- Security: metacharacters that are ALWAYS blocked (no confirmation) ----
BLOCKED_META_CHARS = [";", "&&", "||", "`", "$(", "${", "\n"]

# ---- Security: paths that are ALWAYS blocked (no confirmation) ----
BLOCKED_PATHS = [
    "/etc", "/root", "/proc", "/sys", "/dev",
    "/boot", "/lib", "/lib64", "/usr/lib",
    "/var/log", "/var/spool/cron",
    "/home/*/",
]

# ---- Security: max argument length ----
MAX_ARG_LENGTH = 4096
# ============================================================


def check_command(core_args: list[str]) -> tuple[str, str]:
    """Return (status, reason).
    status: 'safe' | 'confirm' | 'blocked'
    """

    if not core_args:
        return ("blocked", "Empty command.")

    base_cmd = core_args[0]
    cmd_str = shlex.join(core_args)

    # ---- 1. Hard-block dangerous patterns ----
    for pattern in HARD_BLOCKED_PATTERNS:
        if pattern in cmd_str:
            return ("blocked", f"Dangerous pattern: '{pattern}'")

    # ---- 2. Hard-block shell metacharacters ----
    for char in BLOCKED_META_CHARS:
        if char in cmd_str:
            return ("blocked", f"Shell metacharacter not allowed: {repr(char)}")

    # ---- 3. Hard-block I/O redirection ----
    if re.search(r'(?<![a-zA-Z0-9_\-/.])[<>]', cmd_str):
        return ("blocked", "I/O redirection (>/>>/<<) not allowed.")

    # ---- 4. Hard-block system paths ----
    for arg in core_args:
        for blocked_path in BLOCKED_PATHS:
            if blocked_path in arg:
                return ("blocked", f"Access to blocked path '{blocked_path}' in argument: {arg}")

    # ---- 5. Hard-block oversized command ----
    if len(cmd_str) > MAX_ARG_LENGTH:
        return ("blocked", f"Command too long ({len(cmd_str)} > {MAX_ARG_LENGTH} chars).")

    # ---- 6. Confirm-level: dangerous commands ----
    for cmd in CONFIRM_COMMANDS:
        if base_cmd == cmd or base_cmd.endswith(f"/{cmd}"):
            return ("confirm", f"Potentially dangerous command: '{base_cmd}'")

    return ("safe", "OK")


def prompt_confirm(command: str, reason: str) -> bool:
    """Ask user for confirmation. Returns True if approved."""
    print()
    print("=" * 50)
    print(f"WARNING: {reason}")
    print(f"Command to execute remotely: {command}")
    print(f"Remote server: {SERVER}")
    print("=" * 50)

    try:
        answer = input("Execute anyway? [y/N]: ").strip().lower()
        return answer in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


def build_env(add_pythonpath: bool, add_hf_mirror: bool) -> str:
    parts = []
    if add_pythonpath:
        parts.append("PYTHONPATH=.")
    if add_hf_mirror:
        parts.append(f"HF_ENDPOINT={HF_MIRROR_URL}")
    if parts:
        return " ".join(parts) + " "
    return ""


def main():
    parser = argparse.ArgumentParser(
        description="Forward commands to a remote server via SSH with uv environment.",
        usage="python remote_run.py [options] <command> [args...]",
    )
    parser.add_argument(
        "--raw-env", action="store_true",
        help="Strip both PYTHONPATH and HF_ENDPOINT (uv run only)."
    )
    parser.add_argument(
        "--no-hf", action="store_true",
        help="Don't prepend HF_ENDPOINT."
    )
    parser.add_argument(
        "--no-py-path", action="store_true",
        help="Don't prepend PYTHONPATH=."
    )
    parser.add_argument(
        "--direct", action="store_true",
        help="Don't wrap in 'uv run' at all — forward the command as-is."
    )
    parser.add_argument(
        "-y", "--yes", action="store_true",
        help="Skip confirmation for dangerous commands (for scripting/agents)."
    )

    args, unknown = parser.parse_known_args()

    if not unknown:
        print("ERROR: Please provide a command to forward.")
        print("Usage: python remote_run.py [options] <command> [args...]")
        sys.exit(1)

    # Strip accidental 'uv run' prefix (agent-generated commands)
    if len(unknown) >= 2 and unknown[0] == "uv" and unknown[1] == "run":
        core_args = unknown[2:]
    else:
        core_args = unknown[:]

    if not core_args:
        print("ERROR: No command left after stripping uv run prefix.")
        sys.exit(1)

    # ---- Security check ----
    status, reason = check_command(core_args)

    if status == "blocked":
        print(f"[SECURITY BLOCK] {reason}")
        sys.exit(1)

    if status == "confirm":
        if args.yes:
            print(f"[WARNING] {reason} — auto-confirmed via --yes.")
        elif not prompt_confirm(shlex.join(core_args), reason):
            print("[CANCELLED] User declined.")
            sys.exit(1)
        else:
            print("[CONFIRMED] Proceeding.\n")

    raw_command = shlex.join(core_args)

    # ---- Resolve env flags (CLI overrides config) ----
    use_pythonpath = ADD_PYTHONPATH and not args.raw_env and not args.no_py_path
    use_hf_mirror = ADD_HF_MIRROR and not args.raw_env and not args.no_hf

    # ---- Build the final remote command ----
    if args.direct:
        final = raw_command
    elif core_args[0] in ("python", "pytest", "pip"):
        env = build_env(use_pythonpath, use_hf_mirror)
        final = f"{env}uv run {raw_command}"
    elif core_args[0] == "uv":
        final = raw_command
    else:
        final = raw_command

    ssh_cmd = [
        "ssh", "-t", SERVER,
        f"bash -lc 'cd {REMOTE_DIR} && {final}'"
    ]

    print(f"[Remote -> {SERVER}] {final}")
    print("-" * 50)

    try:
        subprocess.run(ssh_cmd)
    except KeyboardInterrupt:
        print("\n[Remote] Terminated by user.")
    except Exception as e:
        print(f"\n[Remote] Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
