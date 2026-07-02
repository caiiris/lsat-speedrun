#!/usr/bin/env bash
# Speedrun WP-10 — one-command anki-sync-server bring-up (spec-sync-mobile §9).
#
# Usage (from repo root):
#   ./tools/speedrun/sync/start_sync_server.sh
#   SYNC_USER1=alice:secret ./tools/speedrun/sync/start_sync_server.sh
#
# Desktop: Preferences → Syncing → Custom sync server → http://<lan-ip>:8080/
# AnkiDroid: Settings → Advanced → Custom sync server → same URL
# Account: user from SYNC_USER1 (default speedrun / speedrun)

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"

export SYNC_USER1="${SYNC_USER1:-speedrun:speedrun}"
export SYNC_USER2="${SYNC_USER2:-speedrun2:speedrun2}"
export RUST_LOG="${RUST_LOG:-anki=info}"
# A venv on PATH can shadow `ar` with unrelated scripts (e.g. analogical-reasoning).
export AR="${AR:-/usr/bin/ar}"

echo "Starting anki-sync-server on http://127.0.0.1:8080"
echo "SYNC_USER1=${SYNC_USER1}"
echo "SYNC_USER2=${SYNC_USER2}"
echo "Data dir: \${HOME}/.syncserver (override with SYNC_BASE)"
echo ""
echo "Press Ctrl+C to stop."

exec cargo run --quiet --manifest-path rslib/sync/Cargo.toml --release
