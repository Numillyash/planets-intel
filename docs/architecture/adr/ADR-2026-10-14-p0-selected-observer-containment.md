# ADR 2026-10-14: P0 selected-observer containment

**State:** Implemented and deployed (2026-10-14). P0 merged as PR #46; production `88a3282` validated, then superseded by production `616406c` retaining the P0 boundary. This is a code/runtime checkpoint, not a guarantee of comprehensive compliance with external game rules.

Legacy IntelBoard global `DashboardIntelShare` approvals have no game ID,
official diplomacy provenance, field-level disclosure or game-mode scope.
Therefore they cannot authorize one observer to read or refresh another
observer's private turn data. Consent on IntelBoard alone is not evidence
of authorization under Planets.nu rules.

## Temporary P0 policy

- A private aggregate requires an explicit game ID and selected active,
  locally owned primary observer. Only that observer's factual batches may
  contribute. This holds in public, private, team and unknown game modes.
- The server enforces the restriction before source selection. An unknown
  or inactive/unowned observer is denied. Existing turn/batch provenance,
  last-seen info turns and known-zero semantics are preserved.
- Historical combined, live combined, tracks, combat and host events,
  VCR replay/odds, threat/loadout inference and derived replay each use
  the same selected-observer boundary.
- Background private synchronization refreshes only the local user's
  own linked observers. Legacy peer agreements have no effect.
- Legacy share creation and acceptance are denied. Listing and revocation
  are retained, and old rows are explicitly labelled disabled. No
  implicit conversion of old agreements into game-specific grants.
- Prior analyst-confirmed combat-state observations were stored without
  observer provenance. They are quarantined from reads and writes until
  a provenance-bearing schema can be independently reviewed.
- Public game data, public scores, independent inference and single
  observer private histories are unaffected by legacy sharing.

## Risks and later work

P0 is deliberately restrictive. Existing combined views may show fewer
facts, and analyst combat-state editing is temporarily unavailable.
It adds no schema migration and does not delete stored observations.

P1 has introduced directional, revocable `GameIntelGrant` consent records scoped to one game (migration `0020_game_scoped_intel_grants`). It intentionally provides **no cross-player read authority**. Upstream diplomacy provenance, verified disclosure fields and a written interpretation of external Share Intel/Full Alliance restrictions are still required before any private cross-player projection.

## Acceptance gates

Synthetic regression tests for owned-only and unowned primary requests,
cross-game agreement non-authority, background refresh, legacy acceptance,
revoke preservation, derived combat state quarantine and unscoped reads.
CI compile, backend unit tests, frontend build and production image must
pass. This ADR contains no names, private records, API keys or game secrets.
