# Validation checkpoint — VCR presentation, planner stats, scoreboard split, turn timing

Date: 2026-08-19
Branch: `feature/operational-ui`
Baseline checkpoint before this batch: `d05f78098b5a2911ce03b2673167128010a19d1c`
Code head before this handoff: `248cfddda096a5b2ea0015cab10a1cf0ab683cc9`

This batch was driven by live browser validation. It is committed but **not yet runtime-validated on the server**. GitHub currently exposes no commit status checks / PR workflow run for the code head, so a Docker frontend build, backend tests and browser validation are still required after pull.

## 1. VCR combat presentation

User validation confirmed that individual fighters became visible after the prior shared-renderer fix, but exposed four presentation defects:

- large hull artwork (especially Gorbie) overlapped object labels;
- fighter tracks occupied a narrow vertical band;
- fighter-fire / dogfight exchanges were not visually legible;
- ship beams appeared as horizontal forward shots rather than source-to-target lines.

Changes in this batch:

- `CombatReplayPlayer.tsx` now separates deterministic combat X from presentation X and maintains a minimum visual gap between large hulls;
- fighter X is mapped through the same presentation transform as ships and projectiles;
- the 19 deterministic fighter track indices are spread over almost the full battlefield height;
- beam-to-ship, beam-to-fighter and fighter-to-ship shots use an SVG source/target overlay;
- dogfight casualties receive presentation-only exchange lines near the engine-resolved casualty;
- no backend combat RNG or deterministic engine behavior was changed;
- VCR artwork was reduced/reflowed to keep names and `fighters out` readable.

Important provenance note: an exact dogfight shooter identity is not exposed by the classic engine event. The casualty is engine-resolved fact; the nearby connecting line is presentation only and must not be treated as factual shooter attribution.

### Validate

Use a carrier-vs-carrier VCR such as the previously tested Gorbie vs Rush and check:

1. hulls do not cover names or fighter-count text;
2. fighters visibly occupy many vertical lanes;
3. fighter attacks on ships produce visible fighter-to-ship lines;
4. dogfight casualties are visible without implying stored factual shooter identity;
5. ship beams terminate at the actual ship/fighter presentation coordinates;
6. timeline scrubbing remains stable;
7. terminal replay result remains identical to non-visual deterministic replay.

## 2. Replay-based Battle Planner statistics and layout

The VCR validation lab had a visually inconsistent lower deterministic-baseline section and its 10k result only surfaced compact mean terminal text.

The result panels now reuse Battle Simulator-style stat cards and show, per side:

- survival frequency;
- average terminal shield;
- average terminal damage;
- average terminal crew;
- average torpedoes left;
- average torpedoes fired;
- average fighters left;
- average fighters lost;
- survived / destroyed / captured counts.

`Avg torps fired = scenario start torpedoes - mean terminal torpedoes`.

`Avg fighters lost = scenario start fighters - mean terminal fighters`. This is meaningful for this deterministic engine because surviving launched fighters are returned before its terminal result is produced. It is **not** labelled as fighters launched or current factual ammo.

The factual source-seed baseline and source-seed what-if result now use the same responsive terminal stat-card layout.

### Validate

- run 10,000 battles on VCR #40 with factual ammo and with edited ammo;
- verify displayed starting assumptions match the input;
- compare average terminal fields against the standalone Battle Simulator for an equivalent setup where applicable;
- confirm no simulated result is persisted as factual intel.

## 3. Scoreboard de-cluttering

The old Scoreboard stacked five conceptually separate tools in one long page. It is now split into focused tabs:

- `Scoreboard`: public player table + Military Score history chart only;
- `Military intel`: Military Score attribution + VCR fighter evidence;
- `Turn timing`: player turn-behavior timing distributions.

This keeps the score comparison page compact while preserving the forensic panels elsewhere.

### Validate

- Scoreboard should open with the player table and Military Score chart, without attribution/fighter/timing panels below it;
- Military intel should contain attribution and VCR combat fighter evidence;
- historical turn mode must retain the same evidence-boundary behavior as before.

## 4. Multimodal turn timing

The previous UI reduced first-open / ready behavior to one circular average. That hides real multimodal behavior (for example, a player who regularly acts either in the morning or in the evening).

Backend activity analysis now additionally returns the factual per-turn UTC minute-of-day samples:

- `open_utc_minutes`;
- `ready_utc_minutes`.

The existing `typical_*` fields remain for API compatibility but are no longer the primary presentation.

The new `Turn timing` panel displays per player:

- a 24-bin local-hour histogram for first observed Open;
- a 24-bin local-hour histogram for exact Ready time when Planets.nu provides `turnreadydate`;
- current state and sample confidence;
- median Open-after-host and Ready-after-host latency.

The browser converts UTC samples to its local timezone at presentation time. Open observations remain polling-bounded; Ready is exact only when `turnreadydate` is available.

### Validate

- a player with morning/evening behavior should show separate peaks rather than a midday average;
- 00/06/12/18/24 axis must reflect the browser's local timezone;
- players with no samples should not fabricate bars;
- current dead players remain hidden from this operational timing panel as before;
- changing historical `dashboardTurn` must restrict analysis through that turn.

## Tests / build status

Added unit coverage for preserving separate minute-of-day samples, including timezone normalization, in `backend/tests/test_player_activity_state.py`.

At handoff creation time:

- GitHub combined status for `248cfddd...`: no statuses reported;
- commit-associated PR workflow runs: none reported;
- therefore frontend TypeScript/Vite build and full backend tests are **not claimed as passed** for this batch.

Recommended deployment validation commands after pulling this branch:

```bash
cd /opt/planets-intel

git fetch origin
git pull --ff-only origin feature/operational-ui

docker compose build backend
docker compose run --rm backend python -m unittest discover -s tests -v
docker compose up -d
sleep 5
curl -fsS http://127.0.0.1:18080/api/health
```

If the image build fails at `npm run build`, fix that before recreating the running backend.

## Deferred / follow-up

Do not silently expand scope during validation. Record defects and continue from this checkpoint after the live test.

Still requires explicit browser/runtime validation:

- VCR beam/fighter geometry at multiple battle phases and hull sizes;
- exact visual readability of Gorbie and other oversized artwork;
- dogfight presentation clarity;
- 10k planner statistic layout at desktop/mobile widths;
- Turn timing with real multi-turn data and browser timezone conversion;
- Scoreboard/Military intel/Turn timing tab ergonomics;
- full backend suite and production frontend build.
