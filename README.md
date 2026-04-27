# code-relay

> Local dev, remote run — a lightweight bridge between your editor and a GPU server.

Two scripts that optimize the "code locally, execute remotely" workflow. Designed for AI experiments using `uv` and HuggingFace, but useful for any project that needs fast local-to-remote iteration without git-push-sync-pull overhead.

## Why?

- **Agent-friendly** — AI coding agents can run tests and experiments on the remote server via a single command
- **No remote setup** — keep your GPU server clean; no need to install editors, dev tools, or clone repos manually
- **Lighter than git** — `rsync` pushes only changed bytes, instantly; no commits, no pulls, no merge conflicts
- **Safe by default** — dangerous commands require confirmation, shell injection is blocked outright

## Scripts

### `remote_run.py` — Remote command executor

Type commands locally, they execute on the server inside `uv run`.

```bash
# Train on the remote GPU
python remote_run.py python train.py --batch_size 32

# Run tests remotely
python remote_run.py pytest tests/test_model.py

# Install a package on the server
python remote_run.py pip install transformers
```

**Features:**
- Wraps `python`/`pytest`/`pip` in `uv run` with configurable `PYTHONPATH` and `HF_ENDPOINT`
- Strips accidental `uv run` prefixes from agent-generated commands
- SSH with pseudo-terminal (`-t`) for real-time output streaming
- Built-in security: two-level safety gate before any remote execution

**Security model:**

| Level | What triggers it | Behavior |
|-------|-----------------|----------|
| Hard-block | Shell metacharacters (`;`, `\|\|`, `` ` ``), I/O redirect (`>`, `<`), system paths (`/etc`, `/root`) | Rejected immediately |
| Confirm | `rm`, `sudo`, `shutdown`, `docker`, `iptables`, and ~30 others | Prints a warning and asks `[y/N]` |
| Safe | Everything else | Runs directly |

```bash
# Confirmation prompt for dangerous commands
python remote_run.py rm outdated.pt
# → WARNING: Potentially dangerous command: 'rm'
# → Execute anyway? [y/N]:

# Skip confirmation (for agents / scripting)
python remote_run.py -y rm outdated.pt
```

**CLI flags:**

| Flag | Effect |
|------|--------|
| *(default)* | `PYTHONPATH=. HF_ENDPOINT=... uv run <cmd>` |
| `--no-py-path` | Remove `PYTHONPATH=.` |
| `--no-hf` | Remove `HF_ENDPOINT` |
| `--raw-env` | Remove both, just `uv run <cmd>` |
| `--direct` | No `uv run` at all — forward as-is |
| `-y`, `--yes` | Skip confirmation prompts |

### `sync.sh` — Live file sync watcher

Watches local files with `fswatch` and pushes changes to the server via `rsync` in real time.

```bash
./sync.sh
```

Skips `.git`, `.venv`, `checkpoints/`, `logs/`, `__pycache__/`, `data/` by default (configurable).

Requires `fswatch`: `brew install fswatch`

## Configuration

All config lives at the top of each script — no config files, no environment variables needed.

**`remote_run.py`:**
```python
SERVER = "user@host"               # SSH address
REMOTE_DIR = "/home/user/project/" # Remote project root

ADD_PYTHONPATH = True              # Prepend PYTHONPATH=.
ADD_HF_MIRROR = True               # Prepend HF_ENDPOINT (mirror)
HF_MIRROR_URL = "https://hf-mirror.com"

CONFIRM_COMMANDS = [...]           # Commands that prompt for confirmation
HARD_BLOCKED_PATTERNS = [...]      # Patterns always rejected
BLOCKED_META_CHARS = [...]         # Shell metacharacters always rejected
BLOCKED_PATHS = [...]             # Paths always rejected
```

**`sync.sh`:**
```bash
LOCAL_DIR="/path/to/local/project/"
REMOTE_HOST="server_alias"
REMOTE_DIR="/path/to/remote/project/"

EXCLUDES=('.git' '.venv' 'checkpoints/' ...)
```

## Workflow

1. **Start sync** — `./sync.sh` keeps local and remote code in sync
2. **Run remotely** — `python remote_run.py <command>` executes on the server
3. **Develop freely** — write code locally as if everything runs on your machine

## Requirements

- Local: `fswatch`, `rsync`, Python 3.8+
- Remote: `uv`
- SSH key-based auth to the server (set up in `~/.ssh/config`)
