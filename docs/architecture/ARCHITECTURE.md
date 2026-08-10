# Planets.nu Intel Client — Architecture

## Purpose

Planets.nu Intel Client is a read-only intelligence and analytics layer for
Planets.nu.

The system stores not only the current visible state, but also historical
observations and analytical conclusions derived from public statistics and
player-visible information.

## Core rule

Observed facts and inferred information are separate concepts.

An inference MUST NOT overwrite or masquerade as an observation.

## Layers

### 1. Planets.nu adapter

Location:

    backend/app/planetsnu/

Responsibilities:

- communication with Planets.nu API;
- parsing upstream responses;
- transport errors;
- upstream API compatibility.

It must not contain intelligence logic.

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

### 4. Inferences

Location:

    backend/app/intel/inference/

An inference represents a conclusion derived from observations or statistics.

Examples:

    Planet 184 is probably an active shipbuilding world
    Player 3 probably constructed a capital ship on turn 58
    Unknown ship is probably a carrier

Every inference must retain:

- evidence;
- algorithm/rule;
- confidence;
- creation turn.

### 5. Statistics

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

### 6. Solvers

Location:

    backend/app/intel/solvers/

Future analytical components:

- military-score delta solver;
- probable ship construction;
- fleet composition constraints;
- economic activity estimation.

### 7. API

Location:

    backend/app/api/

Provides application data to the frontend.

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

### MVP 0.1

Public read-only mode:

- load game by ID;
- Planets.nu loadinfo;
- Planets.nu loadscores;
- canonical game/player data;
- public score history;
- map;
- statistics UI.

### MVP 0.2

Private player data:

- API key;
- loadturn;
- own objects;
- visible enemy intelligence.

### MVP 0.3

Historical intelligence:

- observations;
- provenance;
- intel age;
- historical planet/ship state.

### MVP 0.4

Multi-user intelligence aggregation.

### MVP 0.5

Inference Engine.

### MVP 0.6

Military-score and fleet composition solver.
