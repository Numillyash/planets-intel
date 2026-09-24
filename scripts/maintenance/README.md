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
- `diagnose-private-refresh-bridge.sh` — production-side proxy/private-refresh transport diagnostic; after the proxy endpoint is reachable it delegates to one bounded stale-target refresh instead of running the whole scheduler batch.
- `diagnose-private-refresh-target.sh` + `.py` — target-progress diagnostic that inventories stale canonical/private turn mismatches only for observers that are not known non-members, probes the configured proxy from the backend container without assuming the `/time` response is JSON, selects one stale game, prints START/timeout/result explicitly, refreshes only that game, and verifies the post-refresh observer turns.
- `diagnose-private-loadturn-account.sh` + `.py` — read-only raw `game/loadturn` diagnostic for the highest-turn stale in-game observer; uses the stored credential without printing it, goes through the configured proxy, and reports only transport/HTTP/API metadata plus a bounded response preview on invalid JSON.
- `diagnose-wsl-proxy-bridge.sh` — WSL-side Tinyproxy/listener/local-proxy diagnostic for the Windows/WSL bridge host.
- `diagnose-windows-proxy-bridge.ps1` — Windows-side ZeroTier/portproxy/listener diagnostic for the bridge host.
- `diagnose-windows-wsl-proxy-bridge.ps1` — combined Windows + default-WSL diagnostic; checks ZeroTier, IP Helper, portproxy, the Windows listener, current WSL IPv4, Tinyproxy and the local WSL proxy path in one run.
- `repair-windows-zerotier-proxy-bridge.ps1` — bounded Windows repair for the confirmed case where Tinyproxy works in WSL but the ZeroTier-facing bridge port is unreachable; backs up state, recreates the explicit portproxy rule, ensures a scoped firewall rule, restarts IP Helper and verifies TCP + HTTP proxy traversal.

The two movement inspectors stream the checked-out diagnostic source into the
already-running backend container. They therefore do not require a production
image rebuild merely to inspect persisted state after a fast-forward Git pull.

## Operator workflow

Prefer a committed maintenance script over pasting a long shell transcript into
an SSH session. The intended operator interaction is normally:

```text
update checkout -> run one script -> return complete output
```

Scripts should print section headers, decisive return codes and a compact
`DIAGNOSIS=...` line where practical. Diagnostics must be read-only unless the
script name and documentation explicitly identify a repair action.

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
