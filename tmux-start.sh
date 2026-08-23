#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

tmux new -d -s backend  './backend/backend-start.sh'
tmux new -d -s frontend './frontend/frontend-start.sh'

echo "Started tmux sessions: backend, frontend"
echo "Attach with: tmux attach -t backend (or frontend)"
