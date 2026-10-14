# Planets Intel repository hygiene and branch policy

**Baseline:** 2026-10-14. **Scope:** repository organization only; no application
behavior changes and no changes to the running production checkout.

## Branch policy

- **`main`** is GitHub's default branch, canonical development target and
  durable full-history reference.
- **`feature/operational-ui`** is retained as the live production deployment
  reference because the versioned deploy entrypoint explicitly fetches it.
  At the 2026-10-14 accepted baseline both branches point to
  `616406cc47963a762f37da7839bf9c7d63540d67`.
- New work starts from verified `main` and goes through narrow branches/PRs.
  Review, CI and security checks precede merges. Before subsequent deployments,
  explicitly fast-forward the production tracking branch with a reviewed
  merge/lease; **never** silently change the deploy script's branch.
- Avoid force pushes, history rewrites or squash merges of archival integration
  ancestry. The October consolidation PR #49 preserved both parents.
- Keep P0's selected-owned-observer private data boundary and P1's
  `authorizes_private_intel=false` policy hold intact.
- Old experimental `checkpoint/*`, `agent/*`, `feature/*`, `ops/*`,
  `fix/*` and `security/*` branches are *not* active development unless
  explicitly identified by a new task. Do not use their old HEAD as evidence
  of the current feature status.

## Inventory snapshot

At closeout the repository had **over 80 branches** (including many dated
checkpoints and previously merged worktrees), no open PRs, and successful CI
on both `main` and `feature/operational-ui`. There is no value in deleting
them blindly: a branch may contain independent research, a useful recovery
point, or historical work not yet cherry-picked into a stable release.

Branch retirement, if requested in the future, must:
1. Gather an exact current remote branch list and check which tips are
   ancestors of `origin/main`; distinguish ancestry from identical files.
2. Match branches to closed/merged PRs, outstanding issue references,
   research checkpoints and release tags.
3. Exempt `main`, `feature/operational-ui`, unique commits and intentionally
   retained checkpoints.
4. Save a reviewed deletion manifest, use GitHub remote deletion only after
   operator approval, and re-query refs to confirm.
5. Never delete branches from an automated age threshold alone.

Read-only candidate list on a fully fetched local workstation:
```bash
git fetch origin --prune
git branch -r --merged origin/main
```
The command above **does not delete remote branches**. Any future destructive
remote cleanup requires an explicit second decision. This closeout performed
no branch deletion.

## Repository contents and privacy

- `docs/handoff/`: historical evidence/checkpoints; older state is archived,
  not automatically the current production status.
- `docs/architecture/`: current design and the dated P0/P1 ADRs.
- `scripts/deploy/production.sh`: self-updating host deploy; do not replace
  it with ad-hoc large SSH paste blocks.
- `scripts/maintenance/`: versioned diagnostics; prefer one safe command.
- `backend/app/cli/export_validation_dataset.py`: manual read-only research
  exporter retained in the October mainline merge; may output private
  observations and MUST NOT be used to publish private data.
- `backend/app/models/ion_storm_observation.py`: retained historical model
  source, **not** enabled in production ORM/migrations.

Do not commit `log.txt`, other host logs, environment secrets, credentials,
private turn files, user inventories or private research captures.
`.gitignore` protects the root `log.txt` and normal runtime log directories.
Never confuse a Git ignore rule with deletion or with sanitizing Git history.

## Closeout

- PR #46: P0 containment, merged and deployed.
- PR #48: P1 game-scoped consent ledger, merged and deployed, disclosure hold.
- PR #49: long operational branch reconciled into `main` without force.
- PR #47: conflict assessment, closed as superseded.
- Last operator-verified production build:
  `docs/handoff/2026-10-14-production-repository-closeout.md`.

There are no outstanding repository cleanup changes required for production.
