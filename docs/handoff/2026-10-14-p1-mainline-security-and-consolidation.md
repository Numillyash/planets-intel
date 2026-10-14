# 2026-10-14 IntelBoard: P0 deployed, P1 ledger and mainline integration

## Verified GitHub state

- P0 PR #46 merged into feature/operational-ui at 88a3282649c7b6b8ca42d4271d765855ffc7ace9.
- Production operator reports exact P0 deploy OK at that SHA on 2026-10-14.
- Production deployment passed 339 backend tests, frontend build, DB
  revision 0019_commander_intel_cache (head) and API health.
- P1 PR #48 merged into feature/operational-ui at
  14d82068bb741c36b2c67c5cc3fbf1ef1ce0a957.
- P1 adds a directional game-specific consent ledger, migration
  0020_game_scoped_intel_grants, current-roster checks, consent and revoke
  endpoints, unlink revocation, and negative tests.
- P1 is NOT deployed as of this handoff; next production deploy still
  needs the standard build/test/migration/health procedure.
- P1 consent records do NOT grant any cross-player private data read.
  Game-level grants cannot elevate P0's selected-owned-observer boundary.

## Mainline reconciliation

The feature branch had 1177 commits absent from main; main had 14 commits
absent from the feature branch (merge-base f126070cafe23150f1f8f51f5bb15a4ff3230f84).
GitHub PR #47 identified merge conflicts. The intentional reviewed
integration resolution uses the actual operational code tree, preserves
the modern PlanetsNuClient transport/ambiguous-write logic from feature,
and retains two unique mainline artifacts unchanged:

- backend/app/cli/export_validation_dataset.py: manual read-only research
  exporter; it may output private payloads and must never be run against
  production/private accounts without explicit appropriate authorization.
  Do not upload its outputs to public repos/CI logs.
- backend/app/models/ion_storm_observation.py: retained source artifact,
  currently NOT imported into model registry and has NO corresponding
  live schema migration. Not an operational feature; avoid invoking its
  table until a reviewed schema/ingestion design exists.

The previously deleted 0019 mainline ion-storm migration is intentionally
NOT revived; Alembic 0019_commander_intel_cache -> 0020_game_scoped_intel_grants
remains linear. The old main PlanetsNuClient is NOT restored.

This is an explicit two-parent history merge (feature + main), not a
force push, squash of 1177 commits, or reset of the production checkout.
CI must validate the resulting integration tree before merging into main.
The deployment source of truth remains feature/operational-ui until a
separately accepted branch unification and production checkpoint.

## Security invariants

- Shared Intel/Full Alliance upstream disclosure restrictions are not
  implied by bilateral dashboard consent. Native diplomacy status and
  field-level allowed projection remain separate policy work.
- Factual/private observations, derived historical evidence, inference,
  prediction and user orders must stay disjoint.
- Historical info_turn and batch_turn remain distinct, known zero is not
  unknown, and legacy global dashboard shares never grant private access.
- Analyst-confirmed combat annotations without selected observer provenance
  remain quarantined; restoration needs a separate provenance-aware model.
- Do not put actual account identities, private turns or credentials in
  shared diagnostics or GitHub artifacts.
