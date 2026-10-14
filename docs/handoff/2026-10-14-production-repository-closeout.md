# IntelBoard production and repository closeout — 2026-10-14

**Purpose:** final authoritative checkpoint for the P0/P1 security work,
mainline consolidation and production deployment. This record is based
on the operator's reported deployment stdout and GitHub CI/ref inspection,
not independent shell access to the host.

## Final production report (operator-supplied)

```text
Preflight and Git update: OK
HEAD: 616406cc47963a762f37da7839bf9c7d63540d67
Build attempt 1/3: OK
Backend tests: 350 tests, OK
DB before: 0019_commander_intel_cache
DB target: 0020_game_scoped_intel_grants (head)
DB after: 0020_game_scoped_intel_grants (head)
Backend recreate: OK
Health: {"status":"ok","service":"planets-intel-backend"}
DEPLOY OK
```

Host deployment log path, not checked into Git:
`/opt/planets-intel/logs/deploy/20261014-161813-production.log`.

## Verified repository state

- Default/canonical `main` SHA `616406cc47963a762f37da7839bf9c7d63540d67`.
- Production tracking branch `feature/operational-ui` SHA `616406cc47963a762f37da7839bf9c7d63540d67`.
- Last feature branch CI (all four jobs): GitHub Actions run 38570174291,
  **success**. Main's post-merge run 38569918185 also **success**.
- No open GitHub PRs at the time of the housekeeping inventory.
- Mainline PR #49 preserved the old feature ancestry; original old `main`
  had 14 independent commits and the operational branch had 1177.
- The prior dirty/conflicting mainline PR #47 was closed as superseded.
- Unique main-only exporter and ion-storm model files were retained, without
  reinstating an obsolete migration or regressing the current Planets.nu client.

## Security baseline

- **P0 / PR #46:** a selected active, locally owned observer is the sole
  source of private intel reads. Legacy global account shares do not
  authorize other observers or background refresh.
- **P1 / PR #48:** `GameIntelGrant` has game, parties, per-game roster
  identification, proposed disclosure categories, consent and revocation.
  **`authorizes_private_intel=false` even after bilateral consent.**
- Official Share Intel versus Full Alliance scopes and external client
  restrictions still need separately verified diplomacy and field-by-field
  policy proof before any cross-player private data path can be permitted.
- Old analyst-confirmed postcombat records without observer provenance
  remain quarantined. Do not silently restore them based on username,
  former sharing grants or historical caches.
- No database migration beyond `0020` is pending at this checkpoint.

## Current operational instructions

Development PRs target canonical `main`. The production deploy script still
tracks `feature/operational-ui` on the host by design. Do not change that
policy without separate deployment review. Documentation-only closeout
does not require deploying/rebuilding the server.

The immediate maintenance workstream is closed. For future engineering
tasks, inspect actual HEADs and current CI, then read
`docs/architecture/NEW_CHAT_START.md` and
`docs/operations/REPOSITORY_HYGIENE.md`.

No account identities, private game/turn details, secrets or personally
identifying evidence are recorded here.
