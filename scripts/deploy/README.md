# Deployment scripts

## Branch contract (verified 2026-10-14)

`main` is the canonical/default GitHub branch. The production checkout and
self-updating script intentionally continue tracking `feature/operational-ui`.
At the accepted 2026-10-14 deployment both references equalled
`616406cc47963a762f37da7839bf9c7d63540d67`. The production host reported
350 backend tests, Alembic `0020_game_scoped_intel_grants (head)` and health OK.
Do **not** change `DEPLOY_BRANCH` or server checkout automatically just because
`main` is now canonical. A branch/deploy change requires independent review.
Docs-only repository housekeeping requires no production deploy.

## Production deploy

Run from any directory on the production server:

```bash
bash /opt/planets-intel/scripts/deploy/production.sh
```

The script is intentionally self-updating. It:

1. refuses to continue if tracked local changes are present;
2. fetches and fast-forwards `feature/operational-ui` from `origin`;
3. re-executes the freshly pulled copy of itself;
4. validates the recorded production host prerequisite contract;
5. verifies local `HEAD == origin/feature/operational-ui`;
6. builds the production backend image (including the frontend build);
7. runs the full backend `unittest` suite;
8. shows the current and target Alembic revisions and upgrades to `head`;
9. refuses to continue if the database did not reach Alembic head;
10. force-recreates the backend container;
11. waits up to 30 seconds for `/api/health`;
12. prints a compact final HEAD / DB / log summary.

The host dependency source of truth is:

- `infra/production/host-requirements.env`
- `docs/operations/PRODUCTION_PREREQUISITES.md`
- `scripts/maintenance/check-host-prerequisites.sh`

The deploy preflight checks Docker/Compose versions, required host commands,
production DNS state, Docker Registry name resolution and HTTPS connectivity
before starting the image build. This is intended to catch host drift and
network prerequisites explicitly rather than failing later inside BuildKit.

Full command output is written to:

```text
logs/deploy/YYYYMMDD-HHMMSS-production.log
```

On failure the script stops immediately before later destructive/deploy steps and prints the last 100 log lines.

Environment overrides are available when needed:

```text
DEPLOY_BRANCH
DEPLOY_REMOTE
DEPLOY_SERVICE
DEPLOY_HEALTH_URL
DEPLOY_BUILD_ATTEMPTS
DEPLOY_BUILD_RETRY_DELAY
```

Normal production operation should not require these overrides.
