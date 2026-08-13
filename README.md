# Planets.nu Intel Client

Web-based intelligence, analytics and future operational client for Planets.nu.

The current production stage is primarily read-only. The target product is a
full Planets.nu-compatible turn workspace with intelligence layered on top of
the ordinary game UI.

## Stack

- Frontend: React + TypeScript + Vite + PixiJS
- Backend: Python + FastAPI
- Database: PostgreSQL
- Deployment: Docker Compose
- External reverse proxy: existing Apache on host

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

Planned application entry point:

    Apache
      -> 127.0.0.1:18080
      -> Planets Intel frontend gateway
      -> backend / PostgreSQL Docker network

PostgreSQL must not be exposed publicly.

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

- Multi-user intelligence sharing

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
