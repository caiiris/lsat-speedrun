# Spec: Sync & Mobile — two apps, one engine

> How the desktop app and the Android companion share one engine and keep progress
> consistent: self-hosted Anki sync, the documented conflict rule, offline+crash
> behavior, and the AnkiDroid companion that carries the same Rust change.
> Companions: [`prd-speedrun.md`](./prd-speedrun.md) §9.B/§9.F, [`spec-engine.md`](./spec-engine.md),
> [`decisions.md`](./decisions.md) (D-SR7, D-SR8, D-SR4). Engine map:
> [`../../extra/architecture/ANKI_ARCHITECTURE.md`](../../extra/architecture/ANKI_ARCHITECTURE.md) §11.
> **Status:** design locked, unbuilt.
>
> **Authority:** frozen initial design. For current truth read [`decisions.md`](./decisions.md);
> a later decision overrides this doc where they conflict.

## 1. The problem this fills

The app must live at a desk *and* on a phone, sharing the same cards, progress, and
engine — and reviews must flow both ways with **none lost or double-counted**, even
across offline edits and crashes. The hard cap (70% max without a phone that shares
the engine and syncs) makes this load-bearing.

## 2. Goals & non-goals

**Goals**
- Desktop + Android run the **same Rust engine** on the **same deck** (the engine change from spec-engine ships to both).
- **Two-way sync** with a documented **conflict rule**; **offline** review then merge; **crash-safe** (zero corruption).
- Self-hosted so the test is reproducible and independent of AnkiWeb.

**Non-goals**
- iOS (Android-first — D-SR7).
- Real-time/instant sync (a feature-idea; manual/periodic sync is the v1 bar).
- A custom sync protocol (reuse Anki's — D-SR8).

## 3. Grounding (engine reuse)

From the engine map: Anki already has a complete sync stack — `rslib/src/sync/`
(client + protocol) and a standalone **`anki-sync-server`** (`rslib/sync/`), plus
desktop sync UI (`qt/aqt/sync.py`, `mediasync.py`). AnkiDroid runs the same Rust
backend. So "share the engine + sync" is **reuse**, not reinvention — the right
brownfield move, and the Rust change rides the shared backend to the phone for free.

## 4. The mechanic

```mermaid
sequenceDiagram
    participant Ph as Android (AnkiDroid fork)
    participant Srv as self-hosted anki-sync-server
    participant Dk as Desktop

    Note over Ph,Dk: both offline
    Ph->>Ph: review 10 cards (USN=-1 locally)
    Dk->>Dk: review 10 different cards (USN=-1 locally)
    Ph->>Srv: reconnect → sync (send/recv changes by USN)
    Dk->>Srv: sync
    Srv-->>Dk: phone's reviews
    Srv-->>Ph: desktop's reviews
    Note over Ph,Dk: all 20 reviews present once; FSRS recomputed deterministically
```

- **Transport:** Anki's existing sync (collection `/sync/*`, media `/msync/*`), pointed at a **self-hosted `anki-sync-server`** (configured via `SYNC_*` env vars; users via `SYNC_USER1=...`).
- **What syncs:** the existing `cards` / `notes` / `revlog` / `graves` tables — which is exactly what Performance needs (spec-engine §7), so **no new synced table** (D-SR4).

## 5. The conflict rule (7b — written down)

> **Rule:** reviews are **additive** at the `revlog` level and reconciled by Anki's
> USN/graves mechanism. When the same card is reviewed offline on both devices,
> **both review-log entries are retained** (none dropped, none double-counted), and
> the card's FSRS state is **deterministically recomputed** from the merged review
> history. The "winner" for the card's *current scheduling state* is the
> later-timestamped review; the earlier review **remains in history** (it still
> counts toward Performance/calibration).

This is a real, documented rule — not "last write silently wins and the other is
lost." Clock-skew is mitigated by Anki's USN ordering rather than wall-clock alone.

## 6. The sync test (executable — 7b)

1. Airplane-mode the phone; review **10** cards. Offline on desktop; review **10 different** cards.
2. Reconnect both; sync. **Assert all 20** reviews present exactly once (count `revlog` deltas).
3. Review the **same** card offline on both; sync; **assert** the merged result matches §5 (both in history; current state = later review).

## 7. AnkiDroid companion

- **Fork** AnkiDroid; build against the **shared Rust backend** carrying the spec-engine change.
- Port the **commit-then-reveal + drawn-item render** to AnkiDroid's review UI (the engine call `draw_item_for_skill` is shared; only the UI differs).
- Surface the three scores + give-up panel on mobile (same gate, same rules).

## 8. Crash & offline (PRD §9.F)

- **Crash test:** kill each app mid-review **20×** → **zero** corrupted collections (SQLite WAL + Anki's transactional writes make this the default; we verify it).
- **Offline:** with no connection, AI features (spec-ai) degrade cleanly and both apps keep reviewing and still produce all three scores.

## 9. Cold-start / the real risk
- **AnkiDroid build/toolchain** is the schedule risk — budget it before Thursday (the assignment's explicit warning). Mitigation: get a trivial shared-engine review loop running on a device early, before layering the engine change.
- **Sphere of self-hosting:** document a one-command server bring-up so graders can reproduce.

## 10. Acceptance criteria
1. Desktop + Android run the same engine on the same deck; the spec-engine change is present on both.
2. The sync test (§6) passes: 20/20 reviews, none lost/double-counted; same-card conflict resolves per §5 and is documented.
3. Offline review then reconnect merges correctly; phone-offline-mid-sync and wrong-clock cases don't corrupt or double-count.
4. Crash test: 20× kill mid-review on each platform → zero corruption.
5. A self-hosted server bring-up is one command and documented.

## 11. Decisions & alternatives
[`decisions.md`](./decisions.md): **D-SR7** (AnkiDroid fork vs thin client vs iOS), **D-SR8** (self-host anki-sync-server; USN/graves conflict rule), **D-SR4** (no new synced table).

## 12. Out of scope (now), tracked
- iOS via FFI (phase-2).
- Real-time sync / E2E-encrypted sync / CRDT merge (feature ideas, §13 of the brief).

## 13. Product phasing
- **v1:** Android companion + self-hosted two-way sync + conflict/offline/crash tests.
- **Phase-2:** iOS; instant sync; richer conflict UX.

---

<sub>Created with the `iris-plan` skill by Iris Cai · maintained with `iris-log`.</sub>
