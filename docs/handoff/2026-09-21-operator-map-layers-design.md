# 2026-09-21 — Operator map layers bounded extension

This document records the implementation boundary for the second external-tools
workstream. It is an architecture plan, not a second replay system.

## Existing map architecture

The current map already has the correct major integration points:

- `PrivateIntelMap.tsx` owns observer/combined mode, current vs historical turn
  selection and factual entity selection;
- `PixiMapCanvas.tsx` owns the Pixi application/world and composes renderers;
- `mapScene.ts` renders the core factual planet/ship/starbase/stellar scene;
- `minefieldScene.ts` renders factual/derived minefield presentation;
- `historicalTrackScene.ts` renders existing historical ship tracks and current
  VCR/combat contacts;
- `orderVectorScene.ts` renders local-draft/derived movement predictions;
- `hostEventScene.ts` already renders factual explosion notifications;
- `TrackControls.tsx` is an existing precedent for map-local presentation
  controls;
- `OperationalMapOverlay.tsx` and the detail panels provide React UI over the
  Pixi surface.

The current `PixiMapCanvas` render composition is centralized and ordered:

```text
drawMinefields
drawHistoricalShipTracks
drawMapScene
drawOrderVectors
drawCurrentCombatContacts
drawHostEvents
```

That is the extension seam. Do not create another canvas, replay engine or
parallel map state store.

## Layer semantics

Future map controls must preserve:

```text
factual entity/event
!= derived visualization
!= analyst annotation
!= inference
!= prediction/local draft
```

Visibility is presentation state only. Hiding a layer must never delete,
downgrade or mutate the underlying evidence.

## Bounded first map slice

The first implementation should introduce a typed presentation-only visibility
state, for example:

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

The initial PR should only gate existing renderers plus add the control UI. It
requires no DB migration and should not change any source semantics.

Recommended integration:

- keep visibility state in `PrivateIntelMap` or `PixiMapCanvas`;
- add a small `MapLayerControls` React component next to `TrackControls`;
- pass booleans into the existing centralized render composition;
- preserve selection state when a layer is hidden, but close a layer-specific
  floating detail card if its source becomes invisible;
- do not modify `PrivateIntelMap` historical-turn loading.

## Factual spatial events

Two spatial factual event paths already exist and should be generalized rather
than duplicated:

1. VCR/combat events through `HistoricalShipTrack` /
   `drawCurrentCombatContacts`;
2. host explosion reports through `HostEventItem` / `drawHostEvents`.

A later bounded refactor may introduce a presentation-only common map-event
descriptor, but source records must remain typed and traceable back to their
original VCR/host-event provenance.

No event should be copied into a new canonical "map event" fact table merely to
draw it.

## Spatial messages

`PrivateMessageObservation` already stores factual `x` / `y` fields when
Planets.nu supplies them.

A spatial-message layer should therefore reuse the existing communications
storage/API and expose only messages that:

- are already authorized for the current observer/combined-intel context;
- have factual coordinates;
- satisfy the selected turn/view boundary.

The map marker is derived presentation of an existing private message fact.
Message privacy/provenance rules remain owned by the communications layer.

## Analyst annotations

Analyst annotations are the one map feature that would require new persisted
state. They must be a separate analyst-authored model, never fields added to
planet/ship/message observations.

A future model should carry at minimum:

```text
annotation_id
user_id / ownership scope
game_id
turn scope (optional)
x
y
title/body
created_at
updated_at
```

and explicit `source_kind = analyst_annotation` semantics.

Annotation rendering should have its own scene module and visual identity. It
must not look identical to factual host/VCR markers.

## Compact location summaries

Dense locations should be clustered only at presentation time. A compact
location summary can aggregate the visible markers at one coordinate, but its
detail view must retain each member's kind and provenance.

Examples:

- 2 VCRs + 1 explosion report at one coordinate;
- ship/planet factual entities plus one selected spatial message;
- analyst annotation at a coordinate already containing factual events.

The cluster count is a derived visualization, not a new factual count.

## Selection / event bridge

The current map already has layer-specific selection state
(`selectedCombatEvent`, `selectedHostEventKey`) plus window-event bridges.

Do not add more DOM text-search bridges for new layers. New work should use
typed callbacks/state from `PixiMapCanvas` to React panels. Existing bridges
can be migrated incrementally; that migration is not required for the first
visibility-controls PR.

## Delivery order

The bounded order is:

1. presentation-only layer visibility controls for existing renderers;
2. spatial-message markers using existing authorized message facts;
3. compact heterogeneous location summaries;
4. separate analyst-annotation persistence/API/scene;
5. only after those facts and controls are stable, consider higher-level
   inferential map overlays.

This sequence deliberately reuses the existing Time Machine, tracks, VCR,
host-event and communications infrastructure.
