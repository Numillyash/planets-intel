# Planets.nu Intel Client

Web-based intelligence, analytics and future operational client for Planets.nu.

The current production stage is primarily read-only. The target product is a
full Planets.nu-compatible turn workspace with intelligence layered on top of
the ordinary game UI.

## Current verified state — 2026-10-14

- **GitHub:** `main` is the default/canonical branch. `main` and the production tracking branch `feature/operational-ui` both point to `616406cc47963a762f37da7839bf9c7d63540d67` at this checkpoint.
- **Production:** operator-confirmed deploy of `616406cc47963a762f37da7839bf9c7d63540d67`, **350/350 backend tests**, Docker image build OK, migration `0020_game_scoped_intel_grants (head)`, backend recreate OK, HTTP health OK. The runtime log is `logs/deploy/20261014-161813-production.log` on the host (never commit it).
- **Authorization:** P0 permits private observations from the **selected, active, locally owned** Planets.nu observer only. Former global pair-sharing grants no access. P1 adds a per-game, directional, revocable **consent ledger**, not cross-player disclosure authority. Every grant explicitly reports `authorizes_private_intel=false`.
- **Still deliberately unavailable:** peer private `loadturn` aggregation and old analyst combat-state annotations lacking observer provenance. Only an independently reviewed diplomacy/field-policy design can change these boundaries.
- **Deployment:** `scripts/deploy/production.sh` still tracks `feature/operational-ui`; **do not change its default or the server checkout just because `main` is canonical**. Check both branch HEADs and CI before any future release.
- **Sources:** [repository operations](docs/operations/REPOSITORY_HYGIENE.md), [latest closeout](docs/handoff/2026-10-14-production-repository-closeout.md), [P0 ADR](docs/architecture/adr/ADR-2026-10-14-p0-selected-observer-containment.md), [P1 ADR](docs/architecture/adr/ADR-2026-10-14-p1-game-scoped-consent-ledger.md).

## Stack

- Frontend: React + TypeScript + Vite + PixiJS
- Backend: Python + FastAPI
- Database: PostgreSQL
- Deployment: Docker Compose
- External reverse proxy: existing Apache on host

Application language runtimes are containerized: frontend builds use Node 20
and the backend runtime uses Python 3.11. The production host dependency
contract is recorded separately and checked automatically before deployment.

See:

- `docs/operations/PRODUCTION_PREREQUISITES.md`
- `infra/production/host-requirements.env`
- `scripts/maintenance/check-host-prerequisites.sh`

## Architecture

The application separates:

1. Planets.nu API adapter
2. Canonical game database
3. Observed facts
4. Deterministic derived state
5. Inferred information
6. Player statistics/history
7. Intelligence Engine
8. User order drafts / command state
9. Presentation layer

Observed facts, derived state, inferred data and user-issued orders MUST NOT be mixed.

See:

- `docs/architecture/ARCHITECTURE.md`
- `docs/architecture/ROADMAP.md`

## Deployment

Existing services on the host include Apache and Minecraft.

Ports 80/443 are owned by the host web stack and must not be bound directly
by application containers.

Current high-level route:

    Apache (host, HTTPS)
      -> 127.0.0.1:18080 (Docker backend serving API + built frontend)
      -> PostgreSQL (private Compose network)

PostgreSQL must not be exposed publicly.

Production deploy:

```bash
bash /opt/planets-intel/scripts/deploy/production.sh
```

The deploy script self-updates and runs the recorded host prerequisite check
before building the production image.

## Development stages

### MVP 0.1

- Public game loading
- Planets.nu /game/loadinfo
- Planets.nu /game/loadscores
- Game map
- Players
- Public statistics
- Historical score storage

### MVP 0.2

- Private API key support
- /game/loadturn
- Own and visible intelligence

### MVP 0.3

- Historical observations
- Intel age / provenance

### MVP 0.4

- P1 game-scoped consent records implemented, **not** disclosure privileges
- Cross-player private sharing remains disabled pending validated diplomacy and explicit per-field policy

### MVP 0.5

- Inference Engine

### MVP 0.6

- Military-score solver
- Fleet/economic estimation

### MVP 0.7

- Combat intelligence completion
- Deterministic NuHost VCR replay
- Post-combat tactical state and provenance

### MVP 0.8

- Planets.nu-style operational UI shell
- Object-scoped tabs for normal game state, Intel, History and Combat
- Intelligence presented as an overlay on top of the normal game workflow

### MVP 0.9

- Turn planning
- Local order drafts
- Rule validation and turn-wide diff

### MVP 1.0

- Full turn execution through the dashboard
- Planets.nu write adapter
- Ship, planet and starbase orders
- Submission audit and post-submit reconciliation

### MVP 1.1

- Intelligence-assisted turn planning
- Explainable recommendations that can be converted into explicit user drafts
