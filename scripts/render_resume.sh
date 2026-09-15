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
for p in sorted(root.glob("Danila-Surkov*.pdf")) + sorted(root.glob("preview-*.png")):
    data = p.read_bytes() if p.suffix == ".pdf" else b""
    extra = ""
    if p.suffix == ".pdf":
        extra = f"  Count={data[data.find(b'/Count'):data.find(b'/Count')+20]!r}"
    print(f"{p.name:44} {p.stat().st_size:8d} bytes{extra}")
PY
