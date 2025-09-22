#!/usr/bin/env bash
set -euo pipefail

# Prefer TELEGRAM_API_ID/TELEGRAM_API_HASH. Fallback to API_ID/API_HASH from .env
TELEGRAM_API_ID="${TELEGRAM_API_ID:-${API_ID:-}}"
TELEGRAM_API_HASH="${TELEGRAM_API_HASH:-${API_HASH:-}}"

if [[ -z "${TELEGRAM_API_ID}" || -z "${TELEGRAM_API_HASH}" ]]; then
  echo "ERROR: TELEGRAM_API_ID/API_ID and TELEGRAM_API_HASH/API_HASH must be set"
  exit 1
fi

# Ports
PORT="${PORT:-8081}"
HEALTH_PORT="${HEALTH_PORT:-10000}"

# Start Telegram Bot API server (listens on Render PORT)
telegram-bot-api \
  --api-id="${TELEGRAM_API_ID}" \
  --api-hash="${TELEGRAM_API_HASH}" \
  --http-port="${PORT}" \
  --http-listen=0.0.0.0 \
  --dir=/var/lib/telegram-bot-api \
  --temp-dir=/tmp/telegram-bot-api &

# Give the server a moment to boot
sleep 2

# Point our Python bot to the local Bot API server inside the container, unless already set
export BOT_API_BASE_URL="${BOT_API_BASE_URL:-http://127.0.0.1:${PORT}/bot}"
export BOT_API_BASE_FILE_URL="${BOT_API_BASE_FILE_URL:-http://127.0.0.1:${PORT}/file/bot}"

# Launch the Python bot (health server will bind to HEALTH_PORT)
exec python3 main.py
