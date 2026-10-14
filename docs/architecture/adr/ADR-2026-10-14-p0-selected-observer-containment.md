# ADR 2026-10-14: P0 selected-observer containment

**State:** Proposed for review; **not** a deployed authorization guarantee.

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

P1 should introduce directional, revocable `GameIntelGrant` records with
an explicit game, verified player/game membership, diplomacy provenance,
game mode and independently reviewed field-level disclosure. Seek a
written interpretation of native Share Intel/Full Alliance restrictions
before enabling external cross-player aggregation.

## Acceptance gates

Synthetic regression tests for owned-only and unowned primary requests,
cross-game agreement non-authority, background refresh, legacy acceptance,
revoke preservation, derived combat state quarantine and unscoped reads.
CI compile, backend unit tests, frontend build and production image must
pass. This ADR contains no names, private records, API keys or game secrets.
