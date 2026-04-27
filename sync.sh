#!/bin/bash
# ============================================================
# CONFIGURATION — Modify these before use
# ============================================================
LOCAL_DIR=""
REMOTE_HOST=""
REMOTE_DIR="/home/swh/..."

# Patterns to exclude from sync
EXCLUDES=(
    '.git' '.venv' '.DS_Store'
    'checkpoints/' 'logs/' '__pycache__/'
    'data/' '*.pyc'
)
# ============================================================

# Build --exclude flags
EXCLUDE_ARGS=""
for pattern in "${EXCLUDES[@]}"; do
    EXCLUDE_ARGS="$EXCLUDE_ARGS --exclude '$pattern'"
done

echo "Syncing ${LOCAL_DIR} -> ${REMOTE_HOST}:${REMOTE_DIR}"
echo "Excluding: ${EXCLUDES[*]}"

fswatch -o "$LOCAL_DIR" | xargs -n1 -I{} rsync -avz \
    $EXCLUDE_ARGS \
    "$LOCAL_DIR" \
    "$REMOTE_HOST:$REMOTE_DIR"
