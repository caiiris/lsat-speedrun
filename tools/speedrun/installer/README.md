# WP-9 — Desktop installer & clean-machine demo (runbook)

Everything needed to produce a Speedrun desktop installer and prove it on a
**clean machine** (no Rust/Python toolchain), plus the importable demo deck so
the installed app can run a real review session.

This is **additive tooling only** — it drives Anki's existing Briefcase
installer (`qt/installer/`, `qt/tools/build_installer.py`) and the Speedrun seed
builder. It does not modify the build system or the app.

## TL;DR

```bash
# 0. Make the build match HEAD first (see "Rebuild" below — B047).
just build
just wheels                 # builds the anki + aqt wheels the installer bundles

# 1. Build + package the installer (adhoc-signed).
./tools/build-installer      # == RELEASE=2 ./ninja installer
#   → out/installer/dist/anki-<version>-mac-<arch>.dmg   (macOS)
#   → out/installer/dist/*.msi                            (Windows)
#   → out/installer/dist/*.tar.zst                        (Linux)

# 2. Build the importable demo deck for the review recording.
tools/speedrun/installer/make_demo_deck.sh out/speedrun-demo.apkg
```

Then copy the `.dmg` (or platform equivalent) **and** `out/speedrun-demo.apkg`
to the clean machine and follow the checklist below.

## Why these steps

- The installer bundles the `anki` + `aqt` **wheels built from `out/`**, so your
  Rust engine change and the whole Speedrun UI ship automatically. There is no
  Speedrun-specific installer config — it's the stock Anki Briefcase flow.
- `SPEEDRUN_SHELL` defaults to `True` (`qt/aqt/main.py`), so a packaged app
  **opens straight into Speedrun Home** — no env var required.
- A clean install starts with an **empty profile**, so the deck must be imported.
  `make_demo_deck.sh` (wrapping `tools/speedrun/deck/export_deck.py`) produces a
  single importable file for that.

## Rebuild so `out/` == HEAD (B047)

The checked-in `out/` tree can lag `HEAD`. Because the installer bundles wheels
from `out/`, **rebuild before packaging** or you ship stale code:

```bash
git rev-parse --short HEAD          # e.g. d9220b6b2
cat out/buildhash                   # must match; if not:
just build && just wheels
```

## The demo deck (`export_deck.py`)

```bash
# Default: fresh synthetic seed deck → .apkg (additive import; recommended)
tools/speedrun/installer/make_demo_deck.sh out/speedrun-demo.apkg

# Full-collection package (replaces the collection on import; pristine demo)
tools/speedrun/installer/make_demo_deck.sh out/speedrun-demo.colpkg

# Include locally-imported REAL items you own (gitignored; see D-SR39):
PYTHONPATH=out/pylib:pylib:tools/speedrun/deck out/pyenv/bin/python \
  tools/speedrun/deck/export_deck.py --out out/speedrun-real.apkg \
  --import tools/speedrun/deck/imported/<your-import-dir>
```

The `.apkg` contains the 3 notetypes, the `LSAT Speedrun::{Skills,Items,Meta}`
decks (skill + meta cards studied; item pool suspended), the `LSAT Speedrun`
deck-options preset, and scheduling. Verified round-trip: importing into an
empty profile yields 214 cards (38 skill + 163 item + 13 meta) and all four
decks.

## Clean-machine verification checklist (the proof)

On a machine (or fresh user account / VM) **without** the dev toolchain:

1. Copy over the installer artifact + `speedrun-demo.apkg`.
2. **macOS:** the `.dmg` is **adhoc-signed** by default, so Gatekeeper flags an
   "unidentified developer." Open it via **right-click → Open**, or clear the
   quarantine flag: `xattr -dr com.apple.quarantine /Applications/Anki.app`.
   (Proper signing needs `SIGN_IDENTITY=<Apple Developer identity>`; not required
   for the proof.)
3. Launch — confirm it opens into **Speedrun Home** (not the Anki deck list).
4. **File → Import** `speedrun-demo.apkg` (or drag it onto the window).
5. Start a drill / session and answer a few items — confirm the review loop runs
   and scores update. **Record this** (clean-build, install, and review are the
   Wednesday proof artifacts).

## Notes / options

- **Branding:** the app still identifies as "Anki" (bundle `net.ankiweb`, icon)
  via `qt/installer/app/pyproject.toml`. It's a legitimate fork, so shipping as-is
  is fine; rebranding to "Speedrun" (formal_name / bundle / icon) is cosmetic and
  optional.
- **Signing:** set `SIGN_IDENTITY` (macOS/Windows) before `package` for a real
  signature; otherwise artifacts are adhoc/unsigned.
- **Windows/Linux:** same flow — CI uses `tools\ninja installer:build` then
  `qt\tools\build_installer.py ... package` (Windows) and the Linux zip format
  (see `.github/workflows/release.yml` for the exact per-platform steps).
