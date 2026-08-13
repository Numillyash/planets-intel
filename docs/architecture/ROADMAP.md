# Planets.nu Intel Client — Roadmap

This roadmap describes the target product beyond the current read-only intelligence client.

The architectural invariant remains unchanged: factual observations, deterministic derived state, probabilistic inference, and user-issued orders are separate data domains with explicit provenance.

## Current baseline

The current production branch already provides public/private game loading, historical observations and provenance, multi-observer intel aggregation, PixiJS map, structured host-event evidence, factual VCR equipment, deterministic NuHost Classic VCR replay, post-combat tactical state, combat-confirmed contacts, threat analysis, and early loadout/military inference.

## MVP 0.7 — Combat intelligence completion

Goal: finish the current combat/intelligence data model before the large UI rewrite.

- deterministic VCR replay as a first-class derived evidence source;
- analyst-confirmed combat state retained as independent evidence;
- explicit provenance for raw VCR, host report, replay-derived state and analyst confirmation;
- VCR-only ships supported by threat analysis without fabricating `ShipObservation` rows;
- post-combat ammunition, fighters, shield, damage and crew available to downstream analysis;
- regression fixtures for known real combats;
- unsupported combat modes fail closed rather than return approximate results.

## MVP 0.8 — Planets.nu-style operational UI shell

Goal: replace the current collection of diagnostic panels with an interface that follows the mental model of the real Planets.nu client while layering our intelligence on top.

The map remains the primary workspace. Selecting an object opens a persistent context panel instead of unrelated floating debug cards.

### Planet panel

Planned tabs:

- `Planet` — normal current planet state;
- `Economy` — minerals, supplies, clans, natives, taxes and production;
- `Starbase` — base state, storage, tech and construction;
- `Ships` — ships physically present or combat-confirmed at the planet;
- `Intel` — additional observations, age, provenance and confidence;
- `History` — turn-by-turn ownership/economy/contact history;
- `Combat` — VCRs, host outcomes and replay-derived post-combat state;
- `Notes` — user annotations.

### Ship panel

Planned tabs:

- `Ship` — normal ship state;
- `Orders` — mission, waypoint, warp, enemy, friendly code and other current orders;
- `Cargo` — fuel, minerals, supplies, clans, money, torpedoes/fighters;
- `Equipment` — hull, engines, beams, tubes/bays and known loadout;
- `Intel` — observations and inference with provenance;
- `History` — positions, mass history and sightings;
- `Combat` — VCR history, replay and post-combat readiness;
- `Notes` — user annotations.

### Presentation rule

The ordinary game state should be readable first. Intelligence is an overlay, not a replacement for the normal Planets.nu object UI.

- factual current value is the primary value;
- stale observations are decorated with their observation turn;
- combat-derived values are explicitly marked as derived;
- inference is shown separately with confidence/evidence;
- contradictions are displayed rather than silently reconciled.

The redesign should reduce floating windows and consolidate related information into object-scoped tabs, drawers and badges.

## MVP 0.9 — Turn planning and draft orders

Goal: allow a complete turn to be planned inside the dashboard without yet requiring every action to be sent upstream immediately.

Introduce a separate command/order domain. Draft orders MUST NOT mutate observations or canonical upstream state.

Required capabilities:

- edit ship waypoint and warp;
- set mission and mission targets;
- set primary enemy and friendly code;
- plan cargo transfers, unloads and jettison where supported;
- edit planet taxes and build targets;
- manage starbase production, tech and ship construction;
- manage torpedo/fighter construction and transfers;
- show current upstream value vs local draft value;
- validate orders against known game rules;
- identify impossible, conflicting or incomplete orders;
- show a turn-wide diff before submission;
- save and restore local drafts;
- allow intelligence recommendations to pre-fill a draft only after explicit user action.

## MVP 1.0 — Full turn execution through Planets Intel

Goal: make Planets Intel a complete operational client capable of submitting a playable turn to Planets.nu.

### Backend write architecture

Planets.nu writes must live behind the backend adapter. The browser must never directly call Planets.nu write endpoints or receive reusable upstream credentials.

Introduce explicit layers:

1. `OrderDraft` — local user intent;
2. `OrderValidation` — rule and consistency checks;
3. `OrderPlan` — normalized upstream command set;
4. `Planets.nu write adapter` — API transport only;
5. `SubmissionReceipt` — upstream responses and identifiers;
6. `Reconciliation` — reload turn and verify resulting upstream state.

### Submission safety

A turn submission workflow must include:

- explicit user-triggered submit action;
- preview of every changed order;
- stale-turn/conflict detection before writes;
- deterministic ordering of dependent writes;
- partial-failure reporting;
- retry only for operations known to be safe to retry;
- audit log of attempted and accepted upstream changes;
- post-submit `/game/loadturn` reconciliation;
- clear distinction between `draft`, `submitted`, `confirmed upstream` and `host-processed` state.

### Functional target

The dashboard should eventually support all routine actions needed to play a turn without opening the original client, including:

- ship navigation and missions;
- cargo and fuel management;
- transfers between ships, planets and starbases;
- taxes and planetary production;
- starbase construction and shipbuilding;
- friendly codes and enemy settings;
- combat-related preparation;
- turn readiness review;
- final turn submission/ready state where supported by the upstream API.

Exact coverage depends on the Planets.nu write API and must be verified endpoint-by-endpoint before implementation.

## MVP 1.1 — Intelligence-assisted operations

Goal: use the Intelligence Engine to help make the turn, while keeping recommendations distinct from user orders.

Examples:

- highlight threatened planets;
- propose intercept/tow/defense moves;
- suggest rearming after deterministic VCR replay shows empty tubes;
- estimate enemy arrival windows;
- flag unsafe routes, minefield exposure and insufficient fuel;
- explain why a recommendation was generated;
- convert a recommendation into an order draft only through an explicit user action.

The Intelligence Engine must never silently submit an inferred action.

## Cross-cutting work

- historical intel quality and provenance;
- host-event parser expansion;
- Unlimited Fuel / engine constraints;
- military-score and construction solver;
- fleet grouping and destination inference;
- tests using real saved game fixtures;
- branch consolidation and CI;
- responsive desktop-first UI;
- performance for long histories and large maps.
