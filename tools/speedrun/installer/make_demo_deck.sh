#!/usr/bin/env bash
# Build the Speedrun demo deck package for the clean-machine install demo (WP-9).
#
# Produces a single importable file so a freshly-installed Speedrun app can load
# the exam deck in one File -> Import step. Defaults to .apkg (additive import);
# pass a .colpkg path to build a full-collection package instead.
#
# Usage:
#   tools/speedrun/installer/make_demo_deck.sh [OUT]
#   tools/speedrun/installer/make_demo_deck.sh out/speedrun-demo.apkg
#   tools/speedrun/installer/make_demo_deck.sh out/speedrun-demo.colpkg
set -euo pipefail

# repo root = three levels up from tools/speedrun/installer/
cd "$(dirname "$0")/../../.."

OUT="${1:-out/speedrun-demo.apkg}"

if [[ ! -x out/pyenv/bin/python ]]; then
  echo "error: out/pyenv/bin/python not found. Run 'just build' (and 'just wheels') first." >&2
  exit 1
fi

PYTHONPATH=out/pylib:pylib:tools/speedrun/deck \
  out/pyenv/bin/python tools/speedrun/deck/export_deck.py --out "$OUT"

echo "Demo deck ready: $OUT"
echo "Import it on a clean install via File -> Import (or drag onto the app)."
