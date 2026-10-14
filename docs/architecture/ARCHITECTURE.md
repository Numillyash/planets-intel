# Planets.nu Intel Client — Architecture

## Purpose

Planets.nu Intel Client is an intelligence, analytics and future operational
client for Planets.nu.

The current production stage is primarily read-only. The target product should
support a complete turn workflow while keeping intelligence layered on top of
the ordinary game state rather than replacing it.

The system stores not only the current visible state, but also historical
observations, deterministic derived combat state, analytical conclusions, and
later user-authored order drafts.

## Core rules

Observed facts, deterministic derived state, inferred information and user
orders are separate concepts.

An inference MUST NOT overwrite or masquerade as an observation.

A replay-derived value MUST retain the factual VCR and algorithm used to derive
it.

A user order draft MUST NOT mutate the stored upstream observation that it was
based on.

## Layers

### 1. Planets.nu adapter

Location:

    backend/app/planetsnu/

Responsibilities:

- communication with Planets.nu API;
- parsing upstream responses;
- transport errors;
- upstream API compatibility;
- future write/order transport.

It must not contain intelligence logic. Future write endpoints must remain
behind the backend; the browser must not talk directly to Planets.nu.

### 2. Canonical database

Stores canonical representations of:

- games;
- turns;
- players;
- planets;
- ships;
- starbases;
- public score history.

### 3. Observations

Location:

    backend/app/intel/observations/

An observation represents information actually available from a source.

Every observation should eventually contain provenance such as:

- game;
- turn;
- subject;
- property;
- value;
- source type;
- source player;
- observation time.

Examples:

    Planet 184 owner = Robots at turn 47
    Planet 184 starbase = true at turn 47
    Ship 231 hull = Gorbie at turn 52

### 4. Deterministic derived state

Derived state is computed from factual inputs by a deterministic algorithm and
must preserve both the inputs and algorithm identity.

Examples:

    VCR #2 start torpedoes = 5
    deterministic NuHost replay => post-combat torpedoes = 0

Derived state does not become a `ShipObservation` merely because it is highly
reliable.

### 5. Inferences

Location:

    backend/app/intel/inference/

An inference represents a conclusion derived from observations, deterministic
state or statistics.

Examples:

    Planet 184 is probably an active shipbuilding world
    Player 3 probably constructed a capital ship on turn 58
    Unknown ship is probably a carrier

Every inference must retain:

- evidence;
- algorithm/rule;
- confidence;
- creation turn.

### 6. Statistics

Location:

    backend/app/intel/statistics/

Stores and analyzes public Planets.nu score history.

Initial metrics include:

- planets;
- ships;
- capital ships;
- freighters;
- starbases;
- military score;
- inventory score;
- priority points.

### 7. Solvers

Location:

    backend/app/intel/solvers/

Analytical components include or will include:

- military-score delta solver;
- probable ship construction;
- fleet composition constraints;
- economic activity estimation.

### 8. Orders / command state

Future operational mode introduces a separate command domain.

Required concepts:

    OrderDraft
    OrderValidation
    OrderPlan
    SubmissionReceipt
    Reconciliation

Draft orders represent user intent. They must remain separate from observations
and from inferred recommendations.

A write sequence should conceptually be:

    upstream observed state
            |
            v
       local OrderDraft
            |
            v
      OrderValidation
            |
            v
         OrderPlan
            |
            v
    Planets.nu write adapter
            |
            v
     SubmissionReceipt
            |
            v
      reload / reconcile

Only an explicit user action may submit a draft upstream.

### 9. API

Location:

    backend/app/api/

Provides application data and, in future operational mode, validated command
operations to the frontend.

The frontend must not communicate directly with Planets.nu.

## Frontend

Technology:

- React
- TypeScript
- Vite
- PixiJS

Major feature modules:

    map
    planets
    ships
    players
    intel
    statistics
    combat
    orders (future)

### UI model

The long-term UI should follow the same mental model as the normal Planets.nu
client:

- map as the primary workspace;
- object selection opens one persistent context panel;
- planet and ship information is split into coherent tabs;
- ordinary game state is presented first;
- intelligence, history, combat evidence and inference are additional overlays;
- floating diagnostic panels should be reduced as the operational shell
  replaces the current development-oriented layout.

The design does not require a pixel-for-pixel copy of the upstream client; it
should preserve the familiar workflow and information hierarchy while adding
our intelligence layer.

## Deployment

Production host currently runs other services.

Host-owned ports:

    80      Apache
    443     reserved for Apache HTTPS
    8123    Minecraft map
    25565   Minecraft

Planets Intel must not bind those ports.

Planned production path:

    Internet
       |
       v
    Apache
       |
       v
    127.0.0.1:18080
       |
       v
    Planets Intel application

PostgreSQL remains inside the Docker network and is not exposed publicly.

## Development phases

The detailed product sequence is maintained in `ROADMAP.md`.

High-level milestones:

- MVP 0.1–0.6: public/private data, history, aggregation, inference and solvers;
- MVP 0.7: combat intelligence and deterministic replay;
- MVP 0.8: Planets.nu-style operational UI shell;
- MVP 0.9: local turn planning and order drafts;
- MVP 1.0: full turn execution through Planets Intel;
- MVP 1.1: intelligence-assisted operations.
