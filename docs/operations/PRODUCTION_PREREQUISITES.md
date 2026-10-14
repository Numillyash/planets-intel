# Production prerequisites and dependency contract

This document is the source of truth for host-level prerequisites of the
production installation at `/opt/planets-intel`.

The machine-readable counterpart is:

- `infra/production/host-requirements.env`

The executable check is:

```bash
bash scripts/maintenance/check-host-prerequisites.sh --deploy
```

The production deploy script runs this check automatically after updating
itself from Git.

## Dependency layers

Do not mix host dependencies with application/container dependencies.

### Production host

Required for normal deploy/operation:

- Bash >= 4.2
- Git >= 1.8
- Docker Engine >= 24
- Docker Compose plugin v2 (`docker compose`, not legacy `docker-compose`)
- curl
- standard GNU/Linux utilities used by scripts: grep, sed, awk, tail, tee,
  seq, getent

Normal deploy does **not** require host Node.js and does **not** require host
Python 3.11.

### Host maintenance Python

The current production host has an old system Python. Host-side maintenance
helpers therefore use **Python 3.6 as the compatibility baseline** unless the
script explicitly runs Python inside the backend container.

Rules for new maintenance scripts:

1. Prefer Bash for simple host/network inspection.
2. If host Python is necessary, keep it compatible with Python >= 3.6.
3. Do not use modern annotation syntax (`list[str]`, `str | None`, etc.) in
   host-side helpers.
4. Do not use `from __future__ import annotations` on the production host.
5. For application/database logic, prefer `docker compose exec/run backend
   python ...`, where Python 3.11 is guaranteed by the image.

### Network maintenance

NetworkManager (`nmcli`) is required only for scripts which alter persistent
host network/DNS configuration.

`dig` and `nslookup` are optional diagnostics. On CentOS-family systems they
are normally supplied by `bind-utils`.

## Container/runtime dependencies

Container versions are defined by Docker/Compose and are independent of the
host language runtimes:

- frontend build: `node:20-alpine`
- backend runtime: `python:3.11-slim`
- PostgreSQL: `postgres:16`

The backend Python package manifest is `backend/requirements.txt`.
The frontend npm manifest is `frontend/package.json`.

### Reproducibility status

At the time this document was added, application package resolution is not yet
fully locked:

- `backend/requirements.txt` declares package names but not exact versions;
- `frontend/package.json` uses semver ranges;
- no committed npm `package-lock.json` exists yet.

Do **not** fabricate lock files or pinned versions. A lock must be produced by
real package resolution using the same build images and then committed.
Until that is done, Docker base image majors and application manifests are the
recorded dependency contract, but rebuilding at a much later date may resolve
newer compatible package versions.

## Production DNS facts

On 2026-08-24 production repeatedly failed to build because NetworkManager had
configured `8.8.8.8`, while direct UDP/53 to that resolver timed out from the
host. The following resolvers were verified reachable:

- `1.1.1.1`
- `9.9.9.9`

Persistent production configuration was changed through NetworkManager rather
than by editing `/etc/resolv.conf` directly.

The repair helper is:

```bash
bash scripts/maintenance/fix-networkmanager-dns.sh
```

It creates a rollback script under `logs/maintenance/` before changing active
profiles.

Docker BuildKit needs DNS and HTTPS access to `registry-1.docker.io` to resolve
base-image metadata. The deploy preflight therefore verifies both before
starting the expensive build step.

## Preflight modes

Normal deploy contract:

```bash
bash scripts/maintenance/check-host-prerequisites.sh --deploy
```

Include NetworkManager/diagnostic command checks:

```bash
bash scripts/maintenance/check-host-prerequisites.sh --network
```

Run both groups:

```bash
bash scripts/maintenance/check-host-prerequisites.sh --all
```

## Adding a new dependency

Any new external requirement introduced by production or maintenance code must
be recorded in the same change that introduces it:

1. application library -> `backend/requirements.txt` or `frontend/package.json`;
2. Docker/runtime version -> Dockerfile/Compose and, when relevant,
   `infra/production/host-requirements.env`;
3. host command/package -> `infra/production/host-requirements.env` and this
   document;
4. executable host requirement -> add/check it in
   `scripts/maintenance/check-host-prerequisites.sh`;
5. optional troubleshooting tool -> document it as optional rather than making
   production deploy depend on it implicitly.

No script should silently assume a new host package or interpreter feature.
