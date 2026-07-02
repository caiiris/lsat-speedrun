# Speedrun — self-hosted sync (WP-10 / WP-15)

One-command bring-up of Anki's `anki-sync-server` plus an executable harness for
the spec-sync-mobile §6 sync tests.

## Quick start

```bash
# From the lsat-speedrun repo root (build pylib once)
just build

# Terminal 1 — start the server (default user speedrun:speedrun)
just sync-server

# Terminal 2 — run the harness
python -m tools.speedrun.sync.sync_test
```

Server URL: **http://127.0.0.1:8080/** (LAN IP for phone: `http://192.168.x.x:8080/`).

## Configure clients

### Desktop (Speedrun / Anki fork)

1. Preferences → Syncing → **Custom sync server**
2. URL: `http://<host>:8080/`
3. Sign in with the `SYNC_USER1` credentials (default `speedrun` / `speedrun`)

Or from the shell:

```bash
SYNC_USER1=alice:secret just sync-server
```

### AnkiDroid (WP-15)

1. Settings → Advanced → **Custom sync server** → enable
2. URL: same as desktop (`http://<lan-ip>:8080/`)
3. Deck picker → sync icon → sign in with the same account
4. Two-way sync uses stock AnkiDroid sync UI; the shared Speedrun engine rides in
   the custom `rsdroid-release.aar`.

### Speedrun scores on phone (WP-15)

Deck picker → overflow menu → **Speedrun scores** (native dashboard calling the
`speedrunDashboard` RPC).

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `SYNC_USER1` | `speedrun:speedrun` | First account (`user:password`) |
| `SYNC_BASE` | `~/.syncserver` | Server data directory |
| `SYNC_HOST` | `0.0.0.0` | Bind address |
| `SYNC_PORT` | `8080` | Listen port |
| `SYNC_ENDPOINT` | `http://127.0.0.1:8080/` | Harness target URL |

## Harness coverage (spec-sync-mobile §6)

| Test | Asserts |
|------|---------|
| **ten-plus-ten** | Two offline copies each review 10 different cards; after sync, **20** revlog rows, none lost |
| **same-card conflict** | Both clients review the same card offline; after sync, **2** revlog rows on that card (§5) |

Conflict rule (D-SR8): reviews are additive at the revlog level; FSRS state follows
the merged history. See [`docs/speedrun/spec-sync-mobile.md`](../../docs/speedrun/spec-sync-mobile.md).

## Manual acceptance (phone + desktop)

1. Airplane-mode phone; review 10 cards. Offline on desktop; review 10 others.
2. Reconnect both; sync. Confirm counts match on both devices.
3. Open **Speedrun scores** on phone — Memory / Performance / Readiness (or abstain)
   should match desktop dashboard for the same deck.

## Troubleshooting

- **`import anki` fails** — run `just build`.
- **Connection refused** — start `just sync-server` first; check firewall for LAN sync.
- **Auth failed** — username/password must match `SYNC_USER1`.
- **Full sync loop** — ensure both clients use the same custom server URL and account.
- **Desktop `sync failed: 404 for url ()` while the server terminal only logs `uri="/"`**
  — the dev QtWebEngine debugger used to bind the same port 8080 and shadowed
  `127.0.0.1:8080`, so sync requests hit Chromium DevTools (which 404s `/sync/…`)
  instead of the server. Fixed by moving the debugger to **9222** (D-SR41). If you
  still hit this, confirm nothing else holds 8080: `lsof -nP -iTCP:8080 -sTCP:LISTEN`
  (only `anki-sync-server` should be there) and restart the desktop app.
