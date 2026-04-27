#!/bin/bash
# ============================================================
# CONFIGURATION — Modify these before use
# ============================================================
LOCAL_DIR="/Users/"
REMOTE_HOST="swh@ip"
REMOTE_DIR="/home/"

# Patterns to exclude from sync
EXCLUDES=(
    '.git' '.venv' '.DS_Store'
    'checkpoints/' 'logs/' '__pycache__/'
    'data/' '*.pyc'
)
# ============================================================

# Build --exclude flags (array avoids quote-in-string pitfalls)
EXCLUDE_ARGS=()
for pattern in "${EXCLUDES[@]}"; do
    EXCLUDE_ARGS+=(--exclude "$pattern")
done

echo "Syncing ${LOCAL_DIR} -> ${REMOTE_HOST}:${REMOTE_DIR}"
echo "Excluding: ${EXCLUDES[*]}"

# Initial sync before watching
echo "Running initial sync..."
rsync -avz "${EXCLUDE_ARGS[@]}" "$LOCAL_DIR" "$REMOTE_HOST:$REMOTE_DIR"
echo "Initial sync done. Watching for changes..."

fswatch -o "$LOCAL_DIR" | xargs -n1 -I{} rsync -avz \
    "${EXCLUDE_ARGS[@]}" \
    "$LOCAL_DIR" \
    "$REMOTE_HOST:$REMOTE_DIR"
