#!/bin/bash
# shot.sh <relative-path> <out-name> [width] [height] [budget-ms]
# Renders a page from the site root with headless Chromium into /root/work/.shots/
set -e
CHROME=/root/.cache/ms-playwright/chromium-1243/chrome-linux-arm64/chrome
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT=${SHOT_DIR:-/tmp/shots}; mkdir -p "$OUT"
PAGE="$1"; NAME="$2"; W="${3:-1440}"; H="${4:-1200}"; BUDGET="${5:-4000}"

if [ ! -f "$ROOT/$PAGE" ]; then echo "MISSING: $PAGE" >&2; exit 1; fi

"$CHROME" --headless --no-sandbox --disable-gpu --hide-scrollbars \
  --force-device-scale-factor=1 \
  --window-size="${W},${H}" \
  --virtual-time-budget="${BUDGET}" \
  --screenshot="$OUT/$NAME.png" \
  "file://$ROOT/$PAGE" 2>/dev/null

if [ -f "$OUT/$NAME.png" ]; then
  echo "OK  $OUT/$NAME.png  ($(stat -c%s "$OUT/$NAME.png") bytes)"
else
  echo "FAILED $NAME" >&2; exit 1
fi
