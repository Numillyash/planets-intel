# Planets Intel — New Chat Start

Updated: 2026-08-24 22:36 +03:00

This file is the shortest bootstrap for a completely fresh ChatGPT development chat.

## Source of truth

- Repository: `Numillyash/planets-intel`
- Active development branch: `feature/operational-ui`
- Do not reconstruct implementation state from old chat history.
- First read:
  1. `docs/architecture/NEW_CHAT_START.md`
  2. `docs/architecture/PROJECT_STATE.md`
  3. `docs/architecture/CURRENT_HANDOFF.md`
  4. when touching deploy/host tooling: `docs/operations/PRODUCTION_PREREQUISITES.md`
- Then inspect the actual branch HEAD and server checkout before changing code.

The old `feature/post-combat-ammo-runtime` branch is already an ancestor of `feature/operational-ui`; do not resume development from it.

`main` is intentionally not the current development source of truth and is diverged from the operational branch. Do not merge/reset it merely to start a new chat.

## Durable checkpoint

A GitHub checkpoint branch exists specifically for chat/session recovery:

```text
checkpoint/2026-08-15-intelboard-handoff
```

Continue normal work on `feature/operational-ui`; use the checkpoint only as a recovery anchor.

## Server

```text
checkout: /opt/planets-intel
health:   http://127.0.0.1:18080/api/health
```

The `backend` Docker image builds and embeds the React/Vite frontend, so `docker compose build backend` validates both backend and frontend.

Because the server has an old Git version, prefer:

```bash
git symbolic-ref --quiet --short HEAD
```

instead of relying on `git branch --show-current`.

### Production host dependency contract

Do not guess host packages/interpreter capabilities from a new chat. Read:

- `infra/production/host-requirements.env` — machine-readable contract;
- `docs/operations/PRODUCTION_PREREQUISITES.md` — rationale and package mapping;
- `scripts/maintenance/check-host-prerequisites.sh` — executable preflight.

Important current facts:

- host Node.js is **not** required; frontend build uses `node:20-alpine`;
- host Python 3.11 is **not** required; backend uses `python:3.11-slim`;
- host-side Python maintenance code must remain compatible with the recorded old-system-Python baseline (currently Python >= 3.6 contract) unless it explicitly runs inside the backend container;
- production NetworkManager DNS uses `1.1.1.1` + `9.9.9.9` because `8.8.8.8` repeatedly timed out from this host on 2026-08-24;
- Docker BuildKit requires working DNS/HTTPS access to `registry-1.docker.io` for base-image metadata.

## Operator command delivery rule

For production/SSH troubleshooting, diagnostics and repair workflows, do not
send the operator a large multiline command block when the same work can be
versioned safely in the repository.

Preferred workflow:

1. add or reuse a script under `scripts/maintenance/`;
2. commit/push it to GitHub;
3. run CI when appropriate;
4. merge it into `feature/operational-ui`;
5. ask the operator to run the script and return its output.

A single short bootstrap command such as `git pull --ff-only`, a deploy
entrypoint, or one script invocation is acceptable. Ad-hoc pasted shell
pipelines should be reserved for cases where creating a script would add no
value or GitHub is itself unavailable.

This rule exists because the production server is commonly accessed over SSH
through PowerShell, where pasting large multiline shell blocks is unreliable.

## First commands in the new chat

Run this before any code change:

```bash
cd /opt/planets-intel

git fetch origin
printf 'BRANCH: '; git symbolic-ref --quiet --short HEAD || true
printf 'HEAD:   '; git log -1 --oneline
printf 'DIVERGENCE HEAD...origin: '; git rev-list --left-right --count HEAD...origin/feature/operational-ui
git status --short

docker compose ps
curl -fsS http://127.0.0.1:18080/api/health && echo
```

If deploy/host work is involved, also run:

```bash
bash scripts/maintenance/check-host-prerequisites.sh --all
```

If the tree is clean and the server is behind, use the self-updating production deploy rather than reassembling deploy commands manually:

```bash
bash /opt/planets-intel/scripts/deploy/production.sh
```

The deploy script updates the branch, re-executes its newest copy, validates the host prerequisite contract, builds the image, runs backend tests, applies Alembic migrations, recreates the backend and verifies health.

## Last validated IntelBoard semantics

Hard invariants that must survive future changes:

```text
known zero != unknown
fact != inference != simulation
combat-time evidence != current factual state
```

Confirmed examples in game `682909`:

- own SSD #43: factual `ammo=45` -> UI shows 45 fighters;
- own SSD #62: factual `ammo=25` -> UI shows 25 fighters;
- own SSD #22: factual `ammo=0` -> known zero;
- enemy Rush #63: fighter bays are known, current fighters remain `UNKNOWN` unless factual evidence exists;
- VCR equipment is immutable combat-start evidence and must not overwrite current ship state.

The game-list and `/games/{id}` routes have canonical DB fallbacks so an upstream Planets.nu outage must not make already-known games disappear from IntelBoard.

For full current Communications, Military-delta, movement, VCR, warp-well, order-draft and offline-read details, read `CURRENT_HANDOFF.md`, `PROJECT_STATE.md` and actual Git history/HEAD. Do not assume the older examples in the handoff files are the newest implementation state.
