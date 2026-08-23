# Deployment scripts

## Production deploy

Run from any directory on the production server:

```bash
bash /opt/planets-intel/scripts/deploy/production.sh
```

The script is intentionally self-updating. It:

1. refuses to continue if tracked local changes are present;
2. fetches and fast-forwards `feature/operational-ui` from `origin`;
3. verifies local `HEAD == origin/feature/operational-ui`;
4. re-executes the freshly pulled copy of itself;
5. builds the production backend image (including the frontend build);
6. runs the full backend `unittest` suite;
7. shows the current and target Alembic revisions and upgrades to `head`;
8. refuses to continue if the database did not reach Alembic head;
9. force-recreates the backend container;
10. waits up to 30 seconds for `/api/health`;
11. prints a compact final HEAD / DB / log summary.

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
```

Normal production operation should not require these overrides.
