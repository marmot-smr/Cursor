#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/resume"
CHROME="${CHROME:-/opt/google/chrome/chrome}"

render_pdf() {
  local html="$1"
  local pdf="$2"
  local tmpdir
  tmpdir="$(mktemp -d)"
  "$CHROME" \
    --headless=new \
    --no-sandbox \
    --disable-gpu \
    --disable-dev-shm-usage \
    --user-data-dir="$tmpdir" \
    --no-first-run \
    --no-default-browser-check \
    --no-pdf-header-footer \
    --allow-file-access-from-files \
    --virtual-time-budget=5000 \
    --print-to-pdf="$pdf" \
    "file://$html"
  rm -rf "$tmpdir"
}

render_png() {
  local html="$1"
  local png="$2"
  local tmpdir
  tmpdir="$(mktemp -d)"
  "$CHROME" \
    --headless=new \
    --no-sandbox \
    --disable-gpu \
    --disable-dev-shm-usage \
    --user-data-dir="$tmpdir" \
    --no-first-run \
    --hide-scrollbars \
    --allow-file-access-from-files \
    --force-device-scale-factor=2 \
    --window-size=794,1123 \
    --screenshot="$png" \
    "file://$html"
  rm -rf "$tmpdir"
}

render_pdf "$OUT/danila-surkov-ru.html" "$OUT/Danila-Surkov-System-Analyst-RU.pdf"
render_pdf "$OUT/danila-surkov-en.html" "$OUT/Danila-Surkov-System-Analyst-EN.pdf"
render_png "$OUT/danila-surkov-ru.html" "$OUT/preview-ru.png"
render_png "$OUT/danila-surkov-en.html" "$OUT/preview-en.png"

python3 - <<'PY'
from pathlib import Path
root = Path("/workspace/resume")
for p in sorted(root.glob("Danila-Surkov*.pdf")):
    data = p.read_bytes()
    i = data.find(b"/Count")
    count = data[i:i+18] if i >= 0 else b"?"
    print(p.name, p.stat().st_size, "bytes", count)
PY
