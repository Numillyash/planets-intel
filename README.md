# Planets.nu Intel Client

Web-based intelligence and analytics client for Planets.nu.

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
4. Inferred information
5. Player statistics/history
6. Intelligence Engine
7. Presentation layer

Observed facts and inferred data MUST NOT be mixed.

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
