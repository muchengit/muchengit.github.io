#!/bin/bash
# ==========================================================================
# shot.sh — 无头浏览器截图
#   用法：bash tools/shot.sh <相对路径> <输出名> [宽] [高] [预算ms]
#   例：  bash tools/shot.sh "blog/index.html" "archive" 1440 1400 5000
#   产物：$SHOT_DIR（默认 /tmp/shots）/<输出名>.png
#
# 浏览器自动探测顺序：
#   1. $CHROME 环境变量
#   2. Playwright 缓存 /root/.cache/ms-playwright/**/chrome
#   3. Puppeteer 缓存 /root/.cache/puppeteer/**/chrome-headless-shell
#   4. 系统 chrome / chromium / google-chrome
# 找不到浏览器时打印醒目提示并以 0 退出（不阻塞自动化流程）。
# ==========================================================================
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT=${SHOT_DIR:-/tmp/shots}; mkdir -p "$OUT"
PAGE="$1"; NAME="$2"; W="${3:-1440}"; H="${4:-1200}"; BUDGET="${5:-4000}"

if [ -z "$PAGE" ] || [ -z "$NAME" ]; then
  echo "用法: bash tools/shot.sh <相对路径> <输出名> [宽] [高] [预算ms]" >&2; exit 1
fi
FILE="${PAGE%%\?*}"          # 允许带 ?query（如 ?theme=light）
if [ ! -f "$ROOT/$FILE" ]; then echo "MISSING: $FILE" >&2; exit 1; fi

find_chrome() {
  if [ -n "$CHROME" ] && [ -x "$CHROME" ]; then echo "$CHROME"; return; fi
  local c
  c=$(find /root/.cache/ms-playwright -maxdepth 4 -type f -name chrome 2>/dev/null | head -1)
  [ -n "$c" ] && { echo "$c"; return; }
  c=$(find /root/.cache/puppeteer -maxdepth 6 -type f \( -name "chrome-headless-shell" -o -name "chrome" \) 2>/dev/null | head -1)
  [ -n "$c" ] && { echo "$c"; return; }
  for c in /usr/bin/google-chrome /usr/bin/chromium /usr/bin/chromium-browser /opt/google/chrome/chrome; do
    [ -x "$c" ] && { echo "$c"; return; }
  done
  echo ""
}

BIN=$(find_chrome)
if [ -z "$BIN" ]; then
  echo "⚠️  未找到无头浏览器，跳过截图：$PAGE"
  echo "   可安装：npx --yes @puppeteer/browsers install chrome-headless-shell@stable --path /root/.cache/puppeteer"
  exit 0
fi

EXTRA=""
case "$(basename "$BIN")" in
  chrome-headless-shell) EXTRA="--headless=old" ;;
  *) EXTRA="--headless=new" ;;
esac

"$BIN" $EXTRA --no-sandbox --disable-gpu --hide-scrollbars \
  --force-device-scale-factor=1 \
  --disable-dev-shm-usage \
  --window-size="${W},${H}" \
  --virtual-time-budget="${BUDGET}" \
  --screenshot="$OUT/$NAME.png" \
  "file://$ROOT/$PAGE" 2>/dev/null

if [ -f "$OUT/$NAME.png" ]; then
  echo "OK  $OUT/$NAME.png  ($(stat -c%s "$OUT/$NAME.png") bytes)"
else
  echo "⚠️  截图失败：$PAGE（浏览器：$BIN）" >&2
  exit 0
fi
