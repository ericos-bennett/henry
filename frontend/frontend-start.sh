#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

set -a
[ -f .env ] && source .env
set +a

npm ci
npm run dev
