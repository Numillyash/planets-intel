# Factual Tow production runtime — 2026-09-16

## Production deployment

Production was deployed successfully at:

`ba25acb79a4f58a6d901ecf1fa449e36b370d27a`

Deployment output reported:

- build: OK
- backend tests: 299 passed
- database before/target/after: `0018_tow_target_ship_id (head)`
- backend recreate: OK
- health: `{"status":"ok","service":"planets-intel-backend"}`
- final status: `DEPLOY OK`
- production log: `/opt/planets-intel/logs/deploy/20260916-164942-production.log`

## Runtime diagnosis that led to the fix

For game `684653`, linked account `2`, turn `29`, ship `#79` (EROS CLASS RESEARCH VESSEL), the stored private snapshot already contained factual Tow state:

- `mission = 6`
- `mission1target = 63`
- `warp = 8`
- no local draft row was required for the factual order to exist.

The previous movement-prediction endpoint returned no item for this ship because serialization was draft-driven even though the Tow runtime could build factual Tow outcomes. PR #14 added the effective movement-prediction facade so missing factual Tow tower/target participants are emitted without inventing deterministic finite-fuel endpoints.

Finite-fuel Tow remains fail-closed when Tow-phase fuel/mass state is unavailable.

## Follow-up diagnostic contract

`backend/app/scripts/tow_order_runtime_diagnostic.py` must inspect the same effective movement-prediction facade used by the API, not the older saved-draft-only facade. It must also match target rows by `tow_tower_ship_id`, otherwise a requested tower ship can hide its separately emitted target participant from the diagnostic output.
