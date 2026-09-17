#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/resume"
CHROME="${CHROME:-/usr/local/bin/google-chrome}"
HTML="$OUT/SA_Surkov_D.html"
PDF="$OUT/SA_Сурков_Д.pdf"
PNG="$OUT/preview.png"

tmpdir="$(mktemp -d)"
cleanup() { rm -rf "$tmpdir"; }
trap cleanup EXIT

timeout 25s "$CHROME" \
  --headless=new \
  --no-sandbox \
  --disable-gpu \
  --disable-dev-shm-usage \
  --disable-background-networking \
  --disable-sync \
  --disable-extensions \
  --disable-default-apps \
  --disable-component-update \
  --user-data-dir="$tmpdir" \
  --no-first-run \
  --no-default-browser-check \
  --no-pdf-header-footer \
  --allow-file-access-from-files \
  --virtual-time-budget=4000 \
  --print-to-pdf="$PDF" \
  "file://$HTML" >/tmp/chrome-resume.log 2>&1 || true

python3 - <<PY
import pymupdf
from pathlib import Path
pdf = Path("$PDF")
doc = pymupdf.open(pdf)
print(pdf.name, pdf.stat().st_size, "bytes", "pages", doc.page_count)
pix = doc[0].get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
pix.save("$PNG")
print("preview", pix.width, pix.height)
PY
