# Planets Intel: Two Sharing Modes (Design + Consent Contract)

**2026-10-14 — Draft, NOT deployed.** This document describes two distinct
visibility modes rather than relabelling the old global Combined union.

## Native mode (`native`)

Read only the authenticated user's own Planets.nu turn, including the data
that the upstream Host has already distributed to that observer through
regular in-game diplomacy. Native Host Share Intel and Full Alliance are
different: Share Intel shares owned position, third-party sightings and VCR;
Full Alliance adds most owned planet/ship details; neither shares every field.

No additional remote observer's private snapshot is loaded or aggregated by
IntelBoard. If the user already sees an allied planet through native diplomacy,
it is naturally present in the *user's own* observation where upstream sent it.
No GameIntelGrant is required to read the native snapshot.

## Unrestricted mode (`unrestricted`): intention vs entitlement

Goal: expose additional factual in-game information from a separately
consenting partner without requiring Full Alliance inside Planets.nu. This
would exceed native Share Intel (and may exceed native Full Alliance if
orders/private inventory are included). It is NOT equivalent to a Host setting
and does not modify upstream diplomacy or the game's maxallies limit.

In this first narrow implementation, a sender must **request** unrestricted
mode for a specific game with an explicit, reviewable subset of 15 field
families and the recipient must **explicitly confirm** that mode rather than
simply accept an older P1 consent. Extra optional groups include ship/planet
Friendly Codes, ship orders, ship transfers, starbase inventory and orders,
planet build goals, ship history, wormhole scans, finances/cargo and private
in-game messages. `private_messages` can encompass correspondence with
non-consenting third parties; it requires a separate explicit checkbox and
must never imply those correspondents agreed to redistribution. A P1 record remains in
`consented_pending_policy`; response contains `authorizes_private_intel=false`.
The P0 selected-owned-observer access boundary is unchanged. No code reads
unrestricted data from other observers yet.

Before enabling positive disclosure, explicitly define which factual domains
are in scope (ships, planets, starbases, derived/VCR/historical content),
whether earlier turns count, and whether private messages, own orders,
friendly codes, and user annotations must be excluded. Never share API keys,
session tokens or other account credentials. Prevent cross-game grant reuse,
stale roster identity, revoked rights, transitive graph fan-out and pre-consent
history leaks. Recipient may not use another player's key directly.

A full alliance-like read projection must be built from **explicitly approved
owned-field categories**, not from blind union of `loadturn` data.
A game-specific permission must not auto-promote factual unknown into zero.
All displayed fields retain game, source observer, batch turn and info turn.

## Upstream uncertainty and game rules

Official references:
- https://help.planets.nu/alliances-and-diplomacy
- https://help.planets.nu/API-game-loadturn
- https://help.planets.nu/rules
- https://help.planets.nu/customization

The published `loadturn` specification confirms the API returns the viewing
player's `rst`, but does not comprehensively enumerate all field disclosures
in each diplomacy mode. Do not claim field-level Host equivalence solely
from those docs. Verify via synthetic fixtures or authorized in-game
observations without exporting actual private turn content.

Native disclosure has priority. Whether allowing out-of-Host Full Alliance
equivalence in public games is permitted remains a separate policy question.
Do not represent a mutual IntelBoard grant as native Full Alliance.

## Test requirements

Test native is default; invalid modes fail closed; existing P1 records
remain native; explicit unrestricted confirmation is required at acceptance;
confirmed consent alone does not grant private data; no user-to-user/global
sharing leaks; per-game and revocation boundaries remain enforced. Real data
must not be put in public tests, CI, logs or GitHub attachments.
