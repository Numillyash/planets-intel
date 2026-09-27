# External Planets.nu tools — 2026-09-27 reference catalog

Date: 2026-09-27

Repository: `Numillyash/planets-intel`

This document expands the earlier note
`docs/handoff/2026-09-21-external-tools-intelligence-workstreams.md`.

It records external Planets.nu clients, dashboards, plugins and analysis tools that
are useful as product/UX/API references. It is a source inventory and planning
record, not a claim that third-party implementations are authoritative for
NuHost mechanics.

## Evidence and code boundary

Keep the normal IntelBoard boundaries intact:

```text
official/public Planets.nu observation
!= third-party derived value
!= third-party implementation
!= analyst annotation
!= inference
!= prediction
```

Rules:

- prefer official Planets.nu APIs and our stored observations for factual state;
- external clients/plugins are excellent discovery, UX and candidate-algorithm references;
- do not promote a third-party formula into factual/verified Host behavior without independent evidence;
- do not copy source unless the license is clear and compatible;
- preserve attribution when a license requires it;
- when license status is unclear or contradictory, treat the repository as reference-only.

## High-value external projects

### 1. SteveDraper/Planets-Console

URL: https://github.com/SteveDraper/Planets-Console

Status observed 2026-09-27: active development; Python backend + React/Vite frontend;
repository metadata reports MIT.

Why it matters to `planets-intel`:

- very close product shape to IntelBoard: analytical web console around Planets.nu data;
- BFF/API separation and persistent historical turn storage;
- tabular and map modes;
- selectable analytics and layer controls;
- one-turn reachability / Connections analytics;
- warp-well and gravitonic movement presentation;
- Stellar Cartography overlays: debris disks, star clusters, nebulae, ion storms,
  black holes and wormholes;
- minefield visualization with normal/web separation, stale `infoturn`, owner/stance
  coloring and pre/post-decay rings;
- map options, coordinate readout, tooltips and hover/pinned interaction patterns;
- build inference surfaced as derived analysis rather than raw fact.

Use it primarily as a UX/architecture reference for our existing Pixi map and
analytics surfaces. Do **not** create a parallel map or replay subsystem just
because this project has one.

### 2. j1o1h1n/vgaplanets-sitrep

URL: https://github.com/j1o1h1n/vgaplanets-sitrep

Status observed 2026-09-27: current Python/Textual project.

The repository is already split into domain-oriented modules including:

```text
autotax
econ
econrep
freighters
graph
messages
milint
minefields
space
starmap
transmission
```

Useful product ideas:

- compact turn situation report;
- economy and logistics summary views;
- military-intelligence rollups;
- minefield and message summaries;
- freighter workload / operational logistics views;
- textual/compact presentation of information that does not need a full map.

This is a good reference for a future IntelBoard "SitRep" or compact commander's
summary built from our existing factual and inferred layers.

### 3. ChallengeSY/nu-replayer

URL: https://github.com/ChallengeSY/nu-replayer

Status observed 2026-09-27: actively maintained; repository license file uses the
Expat/MIT-style license.

Important features:

- standalone completed-game downloader;
- turn-by-turn starmap replay;
- arbitrary turn jump and slideshow;
- planet/ship/VCR lists and detailed object reports;
- built-in VCR player;
- automated VCR "what-if" runs summarized as outcome percentages;
- public live-spectator support for Campaign Arena data where available.

IntelBoard relevance:

- Battle Planner UX and repeated simulation presentation;
- Time Machine ergonomics;
- replay controls;
- evidence drill-down from VCR list to combat detail.

Any combat algorithm found there remains a candidate implementation, not Host
truth, until independently verified in `planets-lab`.

### 4. Kecupo/PMS-Planets.nu

URL: https://github.com/Kecupo/PMS-Planets.nu

Status observed 2026-09-27: recent Godot/GDScript offline client work.

Current repository structure exposes useful domain separation:

```text
PlanetsApi
GameSession
GameStorage
TurnData
PlanetData
StarshipData
MinefieldData
IonStormData
NebulaData
StarClusterData
PlanetMath
orders store
planet info panel
starmap
```

README functionality includes login, game selection, turn download/upload,
starmap, Stellar Cartography, friendly-code randomization and native/colonist
taxing.

IntelBoard relevance:

- offline/current-turn object model reference;
- planet information density and tax/economy controls;
- StarMap layer/entity organization;
- order-editing interaction ideas for our local drafts.

No repository license was identified in the quick review, so source should be
treated as reference-only unless license status is confirmed.

### 5. Kecupo/planets-vcr-sim

URL: https://github.com/Kecupo/planets-vcr-sim

Status observed 2026-09-27: recent Godot project.

Notable files include:

```text
combat_engine_thost.gd
combat_rng_thost.gd
combat_simulator_thost.gd
combat_constants.gd
combat_state.gd
classic_vcr.gd
```

IntelBoard relevance is indirect but important:

- Battle Planner comparison target;
- possible UX ideas for combat state and repeated simulations;
- candidate mechanics must go through `planets-lab` validation before production use.

License status was not established in the quick review; reference-only.

### 6. stefanreuther/c2nu

URL: https://github.com/stefanreuther/c2nu

Status observed 2026-09-27: MIT; maintained recently enough to remain useful.

This is a Planets.nu <-> classic PCC/VPA adapter. It implements:

- login/API-key handling;
- game listing and public info;
- arbitrary game/player/turn download;
- raw dump of Nu turn JSON;
- conversion to classic unpacked/RST/VCR data;
- upload of turn commands;
- local mock/serve mode;
- explicit notes about differences between Nu JSON and classic v3 data.

IntelBoard relevance:

- API semantics and transport edge cases;
- historical turn acquisition semantics;
- normalization cross-checks;
- development fixture ideas.

It is especially useful where we need an independent view of Planets.nu response
shapes, but it is not a substitute for our canonical schema or current API
observations.

### 7. drgirasol/nupilot

URL: https://github.com/drgirasol/nupilot

A large Planets.nu userscript despite the tiny README. The code includes:

- Collector / Distributor / Builder / Alchemy / Expander / Terraformer modes;
- cargo-capacity and demand accounting;
- destination and secondary-destination selection;
- fuel/range estimation;
- warp-well handling;
- gravitonic and hull-special handling;
- nearby enemy ship/planet safety zones;
- automated ship targeting.

Potential product use:

- future logistics/planning assistant;
- cargo balance and colony demand visualization;
- route safety / workload suggestions;
- candidate planner explanations for why a ship is idle or assigned.

License caution: the repository root has an MIT license, while the inspected
`nupilot.js` source header declares GPLv3-or-later. Treat source as
reference-only until that ambiguity is resolved. Reimplement ideas rather than
copying code.

### 8. drgirasol/nuWebBounty

URL: https://github.com/drgirasol/nuWebBounty

This plugin scans messages for Crystal Web drain/out-of-fuel reports and records
historical ship observations including ship id/name/hull/owner/location/turn and
whether the ship was otherwise hidden.

This is directly relevant to our Communications -> Observation pipeline:

- spatial message extraction;
- historical hidden-ship evidence;
- message-derived event markers;
- explicit distinction between observed message facts and inferred current ship state.

A useful future acceptance case is: one raw message -> one attributable
location-bearing observation -> map marker -> historical evidence ledger entry.

### 9. drgirasol/nusweepfc

URL: https://github.com/drgirasol/nusweepfc

This plugin scans mine-scan messages for safe-passage information and annotates
reports with the scanning ship's friendly code.

IntelBoard use:

- message classification;
- Safe Passage/diplomacy evidence;
- friendly-code observations;
- spatial mine-scan event markers.

Friendly-code or relationship conclusions must remain observation/inference
aware; do not silently convert a parsed message into global current truth.

### 10. j1o1h1n/vgaplanets-kesselrun

URL: https://github.com/j1o1h1n/vgaplanets-kesselrun

Status observed 2026-09-27: active enough to include 2025 changes; Apache-2.0.

Features:

- persistent trade routes;
- ships assigned to routes;
- per-planet resource allocation targets;
- automatic load/unload;
- waypoint setting and ready-state automation;
- later HYP support;
- uses McNimble Toolkit/FleetManagement.

IntelBoard use:

- future operational logistics planner;
- visual trade-route layer;
- planet resource target/demand model;
- explainable cargo-routing suggestions.

The initial product should remain advisory/local-draft based. It should not
silently send orders.

### 11. dcorboy/VGAPViewer

URL: https://github.com/dcorboy/VGAPViewer

Older GPL turn-by-turn animation project. It downloads historical turn files,
builds a composite scene and animates:

- friendly movement;
- ship/starbase builds;
- friendly/enemy explosions;
- minefields.

IntelBoard use:

- Time Machine visualization precedent;
- historical event interpolation;
- multi-turn scene/event model.

Do not create a second replay subsystem. Reuse our existing Time Machine,
historical tracks and event layers.

### 12. polendri/nurep

URL: https://github.com/polendri/nurep

Unmaintained Rust replay viewer. It downloads completed-game turn information
from each player to reconstruct cluster ownership through time.

Useful mainly as historical precedent for multi-perspective full-game replay and
for identifying old public-game acquisition patterns.

### 13. hijk-planetsnu/NuPlugs and the wider userscript ecosystem

URL: https://github.com/hijk-planetsnu/NuPlugs

The Planets.nu help plugin catalog and GreasyFork ecosystem contain many small,
focused UX ideas. Examples include:

- homeworld warp circles;
- map focus helpers;
- loading automation;
- map filtering;
- message links;
- last-seen enemy ship tracking;
- race-specific aids.

Treat these as a feature-discovery catalog. Small plugins often expose useful
user needs even when their implementation is obsolete.

## McNimble / chmeee.org tool family

Primary catalog:
https://chmeee.org/#planets.nu

The official Planets.nu plugin documentation points to McNimble's catalog and
specifically names tools such as:

- **Redraw and Filter** — keeps the starmap readable through selective rendering;
- **Show Messages** — renders explosions and other message information on the map;
- **Show Notes** — renders notes and provides a compact summary of ships at a location.

Modern Kessel Run also depends on McNimble's **Toolkit** and
**FleetManagement**, which makes the family relevant beyond old legacy-client UI.

Most useful IntelBoard lessons:

1. filtering/layer visibility is a first-class map feature, not an afterthought;
2. message and event provenance belongs on the map when coordinates exist;
3. user notes/analyst annotations can coexist with factual layers only if visually
   and semantically separated;
4. a location with multiple objects needs a compact aggregate summary rather than
   overlapping labels;
5. reusable fleet-selection/management primitives are valuable for later order
   planning.

These lessons align directly with
`docs/handoff/2026-09-21-operator-map-layers-design.md`.

## derblondehans/player-affinity-tool

URL: https://github.com/derblondehans/player-affinity-tool

The tool uses only public Planets.nu endpoints:

```text
/game/loadinfo?gameid=X
/games/list?username=Y&status=2,3
```

Its useful ideas include:

- reconstructing real usernames for dead/replaced slots from join/drop events;
- preserving multiple participation periods;
- pairwise shared-game intersection;
- calculating turn overlap instead of treating co-presence as simultaneous play;
- presenting an N x N player history matrix;
- drill-down to shared games.

This source already informed our Commander Intelligence foundation. Future use
should be incremental:

- matrix visualization as an optional view;
- richer replacement history drill-down;
- historical race/slot context;
- **never** convert shared games into a factual alliance/coordination claim.

The external project's own overlap code can be used as a comparison oracle for
examples, but our implementation must retain our stricter UNKNOWN/provenance
semantics.

## T-Continuum Analyser

URL:
https://analyzerplanetsnu.freeddns.org/

The earlier 2026-09-21 review identified it as useful for:

- public historical game browsing;
- replay/history views;
- player/race statistics;
- finding games by configuration/settings.

IntelBoard use:

- commander/player history UX ideas;
- browsing/filtering historical public games;
- statistics presentation.

Do not ingest its derived statistics as facts when official Planets.nu sources
can be queried directly.

The site was not reliably fetchable by the automated crawler during the
2026-09-27 refresh, so this entry deliberately preserves only the capabilities
already recorded in our earlier reviewed note rather than inventing new ones.

## What belongs in planets-intel vs planets-lab

| External source / idea | planets-intel | planets-lab |
|---|---|---|
| Planets-Console map layers / UI | High: operator map, analytics UX | Medium: independent expected-feature inventory |
| SitRep | High: compact operational summaries | Low/medium: scripted-agent heuristics only |
| nu-replayer | High: Time Machine/Battle Planner UX | High: compare replay/simulator mechanics |
| Kecupo PMS | Medium/high: starmap/economy/order UX | Medium/high: API/object/mechanics candidates |
| Kecupo VCR sim | Medium: Battle Planner UX | Very high: combat differential candidate source |
| c2nu | Medium: API/historical ingestion cross-check | High: turn/VCR format and API adapter reference |
| nupilot | Medium: logistics/planning ideas | High: movement/economy candidate formulas and edge cases |
| nuWebBounty | High: message-derived spatial evidence | High: web-drain message signatures / corpus mining |
| nuSweepFC | High: message/diplomacy evidence | Medium/high: mine/safe-passage evidence mining |
| Kessel Run | High later: logistics drafts/routes | Medium: HYP/cargo/route candidate behaviors |
| VGAPViewer / nurep | Medium: historical visualization precedent | Medium: historical acquisition/replay reference |
| McNimble scripts | Very high: map UX/filter/event/annotation patterns | Low/medium: only mechanics hints, not evidence |
| player-affinity-tool | High: Commander Intelligence | Low: identity/participation metadata only |
| T-Continuum Analyser | Medium/high: public history UX | High: corpus discovery by settings, followed by official ingestion |

## Concrete IntelBoard follow-up

### Near term — operator map

Use the existing Pixi stack. First bounded implementation should be presentation-only
layer visibility, not a new data model:

```text
entities
minefields
historical_tracks
movement_predictions
combat_events
host_events
spatial_messages
analyst_annotations
```

External references:

- Planets-Console for layer-control structure and cartography/mines UX;
- McNimble Redraw/Filter for filtering expectations;
- Show Messages / Show Notes for spatial event and annotation patterns;
- Ship List-style last-seen circles as a possible later historical-intel layer.

### After layer controls — spatial observations

Extend existing factual observations instead of adding a parallel intelligence store:

- location-bearing messages;
- VCR/combat/explosion markers;
- mine-scan / safe-passage observations;
- web-drain observations;
- compact multi-object location summary.

### Later — operational logistics

Candidate future modules, explicitly advisory/local-draft based:

- planet resource targets;
- freighter route plans;
- colony demand/supply balance;
- ship idle reasons;
- fleet task grouping.

References: Kessel Run, nupilot, SitRep and PMS.

### Later — Battle Planner / Time Machine

Use nu-replayer and Kecupo VCR simulator to review:

- repeated simulation UX;
- outcome distribution display;
- replay speed/step controls;
- combat-state inspection.

Mechanics themselves must enter production only after the corresponding
`planets-lab` evidence chain is closed.

## License / authority quick notes

| Source | Quick license state | Usage posture |
|---|---|---|
| Planets-Console | MIT | architecture/UX/code concepts allowed with normal attribution discipline |
| nu-replayer | Expat/MIT-style | compare/reimplement; mechanics still require validation |
| c2nu | MIT | useful API/format reference |
| Kessel Run | Apache-2.0 | useful logistics reference |
| VGAPViewer | GPL | concept/reference unless GPL obligations are intentionally accepted |
| nupilot | root MIT vs JS GPLv3 header conflict | reference-only until clarified |
| Kecupo PMS | not established in quick review | reference-only |
| Kecupo VCR sim | not established in quick review | reference-only |
| SitRep | not established in quick review | reference-only |
| player-affinity-tool | nonstandard "free to use and modify" wording | reimplement; do not assume standard license terms |

## Durable rule

External projects can tell us:

- what users need;
- which edge cases other implementers noticed;
- which APIs/fields deserve inspection;
- which candidate formulas or workflows deserve a differential test.

They cannot by themselves tell us:

- what NuHost definitely does;
- whether a stale/private/public observation is current truth;
- whether two players are allies;
- whether a prediction should be promoted to a fact.
