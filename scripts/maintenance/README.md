# Maintenance scripts

Host-side maintenance scripts are part of the production interface and must not
silently depend on undeclared packages or interpreter features.

Source of truth:

- `infra/production/host-requirements.env`
- `docs/operations/PRODUCTION_PREREQUISITES.md`

Run the prerequisite checker before ad-hoc maintenance:

```bash
bash scripts/maintenance/check-host-prerequisites.sh --all
```

## Interpreter policy

The current production system Python baseline is **Python 3.6**.

Therefore a script using host `python3` must remain compatible with Python 3.6.
For application/database tasks, prefer Python 3.11 inside the backend container:

```bash
docker compose exec -T backend python - <<'PY'
# application-aware diagnostic code
PY
```

Host Node.js is not a production prerequisite. Frontend builds use the Node 20
Docker build stage.

## Current scripts

- `check-host-prerequisites.sh` — validates the recorded host/deploy contract.
- `docker-registry-dns.sh` — read-only resolver, registry and base-image cache diagnostic.
- `fix-networkmanager-dns.sh` — persistent NetworkManager DNS repair with rollback output.
- `activity-thread.sh` — database-level activity/thread diagnostic using PostgreSQL container tools.
- `activity-thread-api.sh` — application semantics diagnostic using backend Python 3.11.
- `inspect-planets-reply-client.sh` — public Planets.nu client inspector; uses host Python and must stay Python 3.6 compatible.
- `inspect-tow-orders.sh` — read-only factual Tow/draft/effective-prediction inspection for selected ship IDs.
- `inspect-movement-blockers.sh` — read-only current-turn inventory of effective movement prediction blocker populations.

The two movement inspectors stream the checked-out diagnostic source into the
already-running backend container. They therefore do not require a production
image rebuild merely to inspect persisted state after a fast-forward Git pull.

## Package mapping for CentOS-family hosts

Names vary by CentOS/RHEL generation, but the relevant package families are:

- `git` -> Git client
- `curl` -> HTTP diagnostics and health checks
- `NetworkManager` -> `nmcli`
- `bind-utils` -> optional `dig` / `nslookup`
- Docker Engine + Compose v2 plugin -> `docker` and `docker compose`

Do not add an installation command to production automation unless the target OS
and package repository are explicitly known. Preflight should report missing
capabilities; provisioning remains an explicit operator action.
