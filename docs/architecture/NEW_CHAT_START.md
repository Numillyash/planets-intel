# Planets Intel — New Chat Start

**Updated:** 2026-10-14 after production deploy and repository mainline reconciliation.

This document is a short bootstrap. **GitHub is the code source of truth.**
Never reconstruct current implementation or production HEAD from previous chat
messages alone.

## Branches and production

- Repository: `Numillyash/planets-intel` (public).
- Canonical development/default branch: **`main`**.
- Production deploy tracking branch: **`feature/operational-ui`** for compatibility
  with the existing CentOS checkout and `scripts/deploy/production.sh`.
- Both branch tips at this checkpoint: `616406cc47963a762f37da7839bf9c7d63540d67`.
- On 2026-10-14 the operator ran the production deploy successfully at this SHA:
  **350 backend tests**, Docker/frontend build OK, Alembic
  **`0020_game_scoped_intel_grants (head)`**, backend recreated, API health OK.
- Latest authoritative checkpoint:
  `docs/handoff/2026-10-14-production-repository-closeout.md`.
- Repository branch/history maintenance:
  `docs/operations/REPOSITORY_HYGIENE.md`.

**Do not deploy a docs-only change or alter the production deploy branch merely
to align names.** Inspect actual current refs and server state first.

## Required reading in a new engineering chat

1. This document, followed by `docs/architecture/PROJECT_STATE.md` and
   `docs/architecture/CURRENT_HANDOFF.md`.
2. `docs/architecture/ARCHITECTURE.md` and `ROADMAP.md` for invariants.
3. The newest dated handoff and relevant subsystem's actual source/tests.
4. For host work: `docs/operations/PRODUCTION_PREREQUISITES.md` and
   `scripts/maintenance/check-host-prerequisites.sh`.
5. `docs/architecture/adr/ADR-2026-10-14-p0-selected-observer-containment.md`
   and `ADR-2026-10-14-p1-game-scoped-consent-ledger.md` before touching
   authorization, private data, sharing, history, refresh or VCR paths.

## Security / evidence boundaries

- One selected, owned, active Planets.nu observer per private read and game.
  No global account pair or historical agreement can widen it.
- P1 game-scoped grants represent proposals/consent only. They are **not**
  permission to fetch, aggregate or disclose anyone else's private `loadturn`.
- Native Share Intel versus Full Alliance have different and limited disclosed
  fields. Explicit upstream diplomacy and field-level compliance remain
  unverified and on policy hold.
- Pre-P0 analyst-confirmed combat-state annotations without observer
  provenance are quarantined, not discarded.
- `known zero != unknown`; `fact != deterministic replay != inference != draft`.
  Preserve observer/game/batch turn/info turn and source provenance.
- Private messages, credentials, real player/account identities, game membership
  inventories and private turn content must not be put into public GitHub,
  shared logs, PR discussions or demonstration fixtures.
- The adjacent `Numillyash/planets-lab` repository is research evidence,
  not a substitute for product provenance/authorization checks.

## Operations

The production host has other services on ports 80/443. The application is
behind the existing host reverse proxy and listens on
`127.0.0.1:18080`; PostgreSQL stays inside Docker networking.

The backend image embeds the React frontend. Host-side maintenance scripts
should remain Bash or Python 3.6-compatible; backend Python runs in a
Python 3.11 container. Do not print environment files or API keys.

Production checkout: `/opt/planets-intel`. Deployment entrypoint:

```bash
bash /opt/planets-intel/scripts/deploy/production.sh
```

Deploy is **not** necessary for docs-only repository housekeeping. For future
runtime work use the self-updating deploy script after reviewed CI rather than
handwritten multiline operator commands.

The recommended diagnostic pattern is a versioned maintenance script with one
short invocation; shell snippets pasted over PowerShell/SSH have previously
been unreliable. The production log and `log.txt` are host-local, not code.

## Older materials

Existing August/September checkpoint branches and dated handoffs describe
historical states. Some contain game-specific research examples; do not copy
them into newly published summaries or imply they are current runtime facts.
Read actual Git history when their chronology matters.
