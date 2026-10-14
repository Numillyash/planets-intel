# P1: game-bound consent ledger under official-diplomacy policy hold

**Recorded:** 2026-10-14. **Status:** DEPLOYED technical consent ledger, production `616406c` with Alembic `0020`; **cross-player private sharing remains BLOCKED**.

## Security argument

The former DashboardIntelShare grants were global and lacked game/diplomacy/
field scope. They cannot legitimately permit raw private loadturn aggregation.
Official Planets.nu Share Intel and Full Alliance disclose different subsets
of information, and even Full Alliance does not transmit all fields.

Documentation:
- https://help.planets.nu/rules
- https://help.planets.nu/alliances-and-diplomacy
- https://help.planets.nu/customization

## Ledger semantics

A GameIntelGrant records a directional request tied to one game, two
independently linked accounts, explicit current active roster slot identity
for both, and an allowlist of *requested* field categories. The grantor
requests consent; only the grantee's local account owner can accept it.
Neither a global legacy share nor ownership of two accounts by one local
user auto-approves anything. The same in-game slot on both sides is denied.
If any current membership information is ambiguous/stale, reject the request.

State machine: pending -> consented_pending_policy -> revoked.
Either participant can revoke. Unlinking either account revokes unrevoked
requests, with archived history retained. Re-request after revocation is
a new record and requires new consent. Game identifiers and requested fields
cannot change on an existing grant.

All API responses include `authorizes_private_intel=false`. The policy
hold is an immutable part of the shipped backend policy: this table
never participates in `accessible_intel_accounts`, historical reads,
background refresh, VCR, Threat or combined source selection. No API
can turn this record into permission.

## External gate

P1 is not **cross-player sharing**. Before a separate positive policy can
be introduced, verify the actual upstream native diplomacy status at the
relevant game/turn, reconcile each individual disclosed field with the
Planets.nu Share Intel / Full Alliance policy, define revocation and
historical exposure semantics, and get written clarification on external
sharing/client use. Even a valid native Full Alliance must not expose
private ship orders, mission targets, waypoints, starbase inventory,
private messages or omitted native fields.

Cross-game authorization bleed remains impossible by construction:
selected local account only is the authoritative raw observation reader.
Do not merge peer raw payloads and attempt to redact afterward.

## Operational acceptance

Migration `0020_game_scoped_intel_grants` adds an independent table; no old
global grants are converted. Deploy must run the existing migration/test
gates. This ADR deliberately contains no real user, key, game, private
turn, allegation or credential content.
