#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

set -a
[ -f .env ] && source .env
set +a

npm install
npm run dev -- --host "${VITE_HOST:-127.0.0.1}"
