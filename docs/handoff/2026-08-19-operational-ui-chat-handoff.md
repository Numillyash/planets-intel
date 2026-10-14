# Planets Intel — Operational UI / Combat / Refresh Handoff

Date: 2026-08-19

This document is the durable record of the long operational-UI development chat that ended on 2026-08-19. GitHub is the source of truth. Do not reconstruct current implementation state from old chat messages.

## Repository / branch / implementation checkpoint

- Repository: `Numillyash/planets-intel`
- Active development branch: `feature/operational-ui`
- Pre-handoff implementation checkpoint: `024f182651882052c51437878e1e69389d48a31e` (`fix: bound optional Planets profile lookups`)
- The handoff documentation commits are intentionally newer than `024f182`; always inspect actual branch HEAD.
- Server checkout: `/opt/planets-intel`
- Health: `http://127.0.0.1:18080/api/health`
- Production `backend` image embeds the React/Vite frontend.

A recovery branch should exist after this handoff is complete:

```text
checkpoint/2026-08-19-operational-ui-handoff
```

Continue normal work on `feature/operational-ui`; the checkpoint is only a recovery anchor.

## Runtime validation at chat end

Confirmed on the real server during this chat:

- production backend image builds successfully, including frontend `npm run build`;
- latest shown full backend suite: `Ran 117 tests ... OK`;
- after a backend recreate the health endpoint returned:

```json
{"status":"ok","service":"planets-intel-backend"}
```

- background refresh scheduler emitted visible `uvicorn` logs and completed iterations;
- new observer-centric `Choose a game` UI was visibly deployed and working in browser;
- the final screenshot showed two observer columns, horizontal game rows and dynamic per-slot turn-state rails.

Important: the final browser screenshot proves the new picker bundle is live, but a fresh chat must still inspect the exact server HEAD and divergence before making changes.

---

# 1. Core intel invariants

These are non-negotiable:

```text
known zero != unknown
fact != inference != simulation
combat-time fact != current fact
current fact != historical fact
missing data != zero
```

Additional rules:

- preserve observer/source provenance before disclosure or merging;
- VCR equipment is factual at combat start and must never overwrite current ship observations;
- deterministic replay is derived evidence, never raw observation;
- unknown Host behavior is fail-closed;
- do not make historical/current claims from first-seen data alone;
- a reused numeric ship ID is not sufficient identity without lifecycle evidence;
- UI presentation changes must not alter deterministic combat RNG/results.

---

# 2. Background private-intel refresh — major architectural change

## What changed

Private refresh is no longer owned only by an open React Dashboard tab.

A backend scheduler now:

- starts shortly after FastAPI startup (currently ~15 s delay);
- runs every 300 s;
- finds active `Running` and `Joining` games;
- refreshes accessible linked Planets.nu observers;
- logs every game result through the Uvicorn-visible logger;
- survives one failed upstream game without aborting the remaining games;
- uses freshness throttling (~4.5 min) to avoid redundant private loadturn calls.

This fixes the old failure mode where data stopped updating while the user was on `/intelboard`, another page, or no browser page at all.

## Joining-game bug fixed

Ceros `#683335` exposed a circular bug:

- canonical DB still said `Joining`;
- scheduler originally considered only `Running`;
- public sync was required to update canonical status;
- public sync never happened because scheduler skipped the game.

Scheduler now includes `Joining`. Runtime probe then returned Ceros turn 4 with all four linked observers cached/refreshed recently.

## Shared-local-user deduplication

There are two local Intel Client users, but both currently share access to the same four linked Planets.nu accounts:

```text
1 georgul
2 helping die
3 mussoleni ii
4 leno4ka
```

`user_id` in scheduler logs is the local Intel Client user, not a Planets player.

The scheduler now deduplicates identical `(game, accessible observer set)` work rather than blindly doing the same four observers once per local user. Different share-sets must remain independent.

## Membership identity edge

Membership checks must use external Planets account ID **or canonical username fallback**. This matters for dead/sentinel/partial identity cases where Planets.nu returns broken or sentinel player identity.

Re-test Chanda after the latest code: historical logs before the final fallback still showed `georgul` and `leno4ka` skipped as “not a player”. The code was changed afterward; runtime confirmation is still desirable.

## Observability

Successful scheduler activity is now visible with:

```bash
docker compose logs --since 10m backend 2>&1 \
  | grep -i "background private refresh"
```

Expected patterns:

```text
background private refresh scheduler started ...
background private refresh user=... game=... turn=... refreshed=... cached=... skipped=... failed=...
background private refresh iteration complete ...
```

---

# 3. Communications / activity ingestion

A complete communication layer was added.

## Sources

The implementation uses both:

- private loadturn `messages` / `mymessages`;
- `/account/ingameactivity` with the required `playerid` request shape.

The latter was reverse-engineered during this chat. A successful request shape is:

```text
apikey + accountid + gameid + playerid
```

Requests without `playerid` fail.

## Persistence / partitioning

- `private_message_observations` migration/model added;
- `game_activity_observations` migration/model added;
- activity is partitioned by the **record’s own gameid**, not by whichever game happened to be requested;
- nested replies are flattened and deduplicated;
- identical upstream IDs in different source collections remain distinct where necessary.

## Semantics

UI now separates communications into:

- General;
- direct conversations by player;
- Activity / system/diplomacy bucket.

Direct-thread replies inherit the private partner from the parent thread.

Ordering rule requested and implemented:

- root/parent messages: newest first;
- replies/children inside a thread: chronological downward;
- replies remain visually indented like Planets.nu.

Chat selection is route/stateful so reloads should keep the selected communications context.

## Important evidence boundary

Player-authored activity that is not proven public/private must remain unclassified rather than silently treated as public chat.

---

# 4. Host / sensor events and explosion intel

Long Range Sensor ship-explosion reports are now parsed into factual host events.

Example factual source discovered in Estes:

```text
headline: Long Range Sensors
body: Distress call and explosion detected at (1684, 1796) the name of the ship was: Scout
```

Rules:

- observed ship name is factual;
- coordinates are factual;
- sensor report does **not** provide ship ID;
- do not infer owner or exact ship identity from name alone;
- explosion does not imply VCR combat: a ship may have struck a mine or died from another non-VCR cause.

Explosion intel appears in the Intel event feed and on the map.

A Patriot mine-hit case showed that mine destruction can be visible as a report even when there is no VCR for that destruction. This is a hard warning against equating “destroyed” with “combat replay exists”.

---

# 5. VCR visual replay — major expansion

The deterministic NuHost classic engine remains the authoritative replay core.

## Visual trace

The trace now exposes engine-derived events for:

- ship beam fire;
- torpedo launches/flight;
- individual fighter launches;
- fighter attacks;
- fighter-vs-fighter/dogfight losses;
- beam attacks against fighters;
- fighter destruction;
- positions for individual fighter tracks.

The implementation was deliberately changed from frame-difference inference to tracing hooks around the deterministic engine stages so no extra RNG calls are introduced.

A test ensures visual tracing does not change the deterministic terminal combat result.

## Presentation geometry

Large hull sprites used to overlap at close physical combat positions. The UI now applies presentation-space separation so sprites remain readable without changing combat coordinates or engine physics.

## Important test lesson

A factual fixture where fighters launch but get beam-killed before firing must not be forced to contain `fighter_attack`. A separate synthetic fixture is used to test `fighter_attack` explicitly.

---

# 6. Standalone Battle Simulator / Battle Planner — major new subsystem

This grew from a replay-only tool into a standalone combat workbench.

## Sources / combatants

The user can add:

- a currently known ship from intel;
- a VCR-only historically observed ship;
- any manual hull from the active game rule catalog;
- a known planet;
- a known planet + starbase.

Manual hull and race are independent simulation inputs. Therefore arbitrary what-if combinations are supported, e.g. a Gorbie with a non-Empire race, unless a selected advantage imposes a rule constraint.

VCR-only ships are explicitly marked combat-time evidence and must not be presented as current ship facts.

This fixed the Chanda issue where known Rush carriers appeared in VCR but were absent from the simulator source picker because the old picker only used current `intel.ships`.

## Adaptive editor

Controls are conditional on actual physical equipment:

- no torpedo selector for a hull with zero launchers;
- no fighter field for zero fighter bays;
- no beam-tech selector for zero beams;
- planet/starbase editor exposes planet defense, base defense, base fighters, beam tech and other relevant fields.

White native form controls were replaced with dark-theme controls in the simulator/replay lab.

## Single battle / visual replay

`Run one` / visual battle uses the same VCR-style player rather than only returning a terminal text state.

## Repeated simulation

The workbench supports repeated battle runs (e.g. 10,000) and reports outcome frequency plus terminal averages such as:

- shields;
- damage;
- crew;
- torpedoes;
- fighters.

Do not label deterministic seed-frequency results as stronger probability claims than the sampled model supports.

## Sequential queues

Ship queues are supported on each side, allowing cases like:

```text
LEFT: Ill Wind -> Victoria
RIGHT: Gorbie
```

State is carried between waves for surviving ships.

## Race / advantage semantics

Required race mechanics are enforced by backend schema/rules, not only frontend:

- Federation Crew Bonus is mandatory for Federation;
- Lizard Crew Bonus / Lizard combat behavior is mandatory for Lizards;
- Fury 2x beam recharge is an explicit optional advantage toggle;
- Privateer 3x beam crew-kill is an explicit optional advantage toggle;
- Galactic Power is explicit and only valid for the Empire context;
- Robot starbase does not receive the shielded-starbase +200 kt mass bonus.

### Lizard vs planet

Do not neutralize the Lizard race in planet combat. The replay core allows the Lizard ship to continue fighting beyond 100% damage according to its racial rule and applies the special post-planet-destruction result semantics. A temporary attempted “fix” to clamp it like a normal ship was recognized as wrong and removed.

## Side / carrier balance

Gorbie is **not inherently always left**.

Two separate concepts exist:

1. race/advantage constraints such as Galactic Power;
2. HOST right-side carrier balance.

Simulator therefore exposes right-carrier balance mode explicitly:

```text
Auto / Force +360 kt / Disabled
```

Two Gorbies can be configured on opposing sides when the selected advantage profile permits it.

## Planet / starbase multi-wave

Supported exactly where Host state transition is understood.

- ship queue vs one fixed planet is supported;
- planet-only defense/fighter carry-over is modeled;
- starbase fighter carry-over can proceed while no undocumented starbase hull-damage transition is required;
- if a surviving starbase receives hull damage and the exact Host formula for resulting base defense/tech state is not proven, the simulation **fails closed as unsupported** rather than applying a guessed proportional formula.

This is intentional and must remain until the exact Host algorithm is reconstructed.

---

# 7. Map / navigation changes

## Warp-well navigation links

Old map links used center-to-center `<=81 ly`, which disagreed with Planets.nu.

Confirmed case in Organia:

```text
Tesmond #28: 2187,2238
Saratoga #74: 2210,2157
center distance: ~84.2 ly
```

Planets.nu still showed a navigation link because a W9 ship can target a discrete coordinate inside Saratoga’s 3 ly warp well. The map link model now evaluates reachable integer grid cells inside the target warp well instead of merely subtracting 3 from a continuous distance or using center distance.

Hard rule: warp-well link reachability is a discrete navigation/grid problem, not simply `center_distance <= 84`.

## Owner labels

Player/owner labels were changed from slot-first/unreadable forms to:

```text
Race / slot N / username
```

Example:

```text
Evil Empire / slot 5 / helping die
```

This formatter is intended for map planet ownership and related operational UI.

---

# 8. Observer-centric game chooser — major UI redesign

The old single observer selector + card grid was replaced by an observer-centric overview.

## Layout

- observer accounts are displayed as independent columns/cards;
- typical desktop layout is two columns because current users have two relevant accounts each;
- implementation must not assume there are only two accounts;
- inside each observer column, games are horizontal rows, not a large card grid;
- joining/finished/running games remain visible with compact metadata.

Final browser screenshots confirmed this layout is live.

## Observer route state

Observer selection is part of the URL:

```text
/intelboard/<observer>
/intelboard/<observer>/<game>
```

Bare `/intelboard` is only a bootstrap route. This prevents Home/reload/bookmark from silently reverting to the first linked account.

## Profile images

Public `/account/loadprofile` returned:

```text
georgul:      account.imageurl = "/33734"
helping die:  account.imageurl = "/37542"
```

`PlanetsAccountResponse` now exposes optional `profile_image_url` presentation metadata.

Rules:

- profile image lookup is optional, not tactical data;
- lookup is bounded with a ~2.5 s timeout;
- account listing must remain usable if profile lookup fails;
- frontend falls back to initials if image loading fails.

## Dynamic player turn-state rail

Each game row shows one compact slot marker per actual game slot. Do **not** assume 8 players: large games can have 20+.

The primary turn-state source is the compact `games/list.turnstatus`, matching Planets.nu game-list semantics. The rail is ordered strictly by slot and must retain empty/dead/computer positions rather than collapsing the order.

Current visual meanings:

- green: turn complete / ready;
- orange: viewed/opened but incomplete;
- light/neutral: unopened where known;
- dark/inactive: dead/inactive;
- separate computer state;
- dotted/unknown: no factual status.

Unknown must remain visually unknown rather than being converted into “unopened”.

Tooltip should expose race / slot / username where player metadata exists.

---

# 9. Planets.nu API observations learned in this chat

## `/account/ingameactivity`

Requires `playerid`. Successful request shape observed:

```text
apikey + accountid + gameid + playerid
```

The response contains `activity[]` with nested `_replies`, `scope`, `activitytype`, source/target metadata, game id and turn.

## `/account/loadprofile`

Observed top-level shape:

```text
account
isregistered
playergroups
success
```

Relevant account fields include:

```text
id
username
description
imageurl
...
```

`imageurl` was observed as a relative path equal in form to the account id.

## loadturn player identity

Planets.nu can return exact unknown-player sentinel values in some dead/edge cases. Partial identity must not be confused with the sentinel. Canonical observer slot / username fallback exists for these cases and should remain conservative.

---

# 10. Point fixes completed in this chat

These are local/targeted fixes rather than architectural changes:

- Alembic revision-id length regression fixed/tested (`alembic_version.version_num` compatibility).
- Private-message migration and game-activity migration added.
- Long Range Sensor explosion parser added and sanitized.
- Explosion map marker added.
- Direct-thread reply indentation/order corrected.
- Communications selection persistence/deep-link behavior improved.
- observer Home/reload fallback fixed with URL observer route.
- Ceros `Joining` refresh target bug fixed.
- background refresh logging made visible in Uvicorn logs.
- duplicate refresh work for identical shared observer sets reduced.
- dead/sentinel membership username fallback added.
- VCR-only ships added to Battle Simulator candidate list.
- simulator native white fields replaced with dark-theme styling.
- no-launcher/no-bay/no-beam editor controls made adaptive.
- repeated simulation terminal averages added.
- visual VCR sprite overlap reduced presentation-side only.
- exact visual combat trace hooks added.
- unsuitable `fighter_attack` factual test replaced with a suitable synthetic fixture.
- discrete warp-well planet-link calculation fixed.
- player owner labels changed to race/slot/name.
- account-game `turnstatus` preserved through backend/API.
- unknown player-slot status stays unknown.
- Planets account profile image lookup added with fail-open fallback and timeout.

---

# 11. Global changes completed in this chat

These are architectural/product-level changes:

1. **Backend-owned continuous intel refresh** rather than browser-owned freshness.
2. **Multi-account shared-intel refresh deduplication** while preserving distinct access sets.
3. **Persistent communications/activity data model** across loadturn and ingameactivity.
4. **Factual host-event layer** for non-VCR tactical events such as long-range explosions.
5. **VCR replay upgraded into a deterministic visual combat trace**, including projectiles/fighters/dogfights.
6. **Standalone Battle Simulator / Battle Planner** built on deterministic combat rather than replay-only UI.
7. **Explicit race/advantage simulation semantics** separated from factual race data.
8. **Sequential combat queues** and conservative planet/base carry-over.
9. **Observer-centric game chooser** replacing the old card-heavy single-observer workflow.
10. **Dynamic game-slot turn-state overview** mirroring Planets.nu operational game-list semantics.

---

# 12. Things that still need runtime testing / verification

These are not necessarily code defects; they are explicit validation tasks.

## A. Server / deploy state

At the start of the next chat, verify actual server checkout:

```bash
cd /opt/planets-intel

git fetch origin
printf 'BRANCH: '; git symbolic-ref --quiet --short HEAD || true
printf 'HEAD:   '; git log -1 --oneline
printf 'DIVERGENCE: '; git rev-list --left-right --count HEAD...origin/feature/operational-ui
git status --short

docker compose ps
curl -fsS http://127.0.0.1:18080/api/health && echo
```

Do not assume the exact deployed SHA from this document alone because handoff commits are newer than the implementation checkpoint.

## B. New game chooser

Validate visually with real data:

- actual Planets profile images vs initials fallback;
- 2-column observer layout on normal desktop;
- responsive behavior with >2 accounts;
- game rows open the correct observer/game route;
- current observer survives reload/Home/back navigation;
- `turnstatus` rail matches original Planets.nu for READY / VIEWED / unopened;
- dead/computer/empty slot colors are correct;
- a 20+ player game wraps/compacts cleanly without hiding slots;
- Joining and Finished rows do not produce misleading “turn complete” semantics.

The final screenshot looked generally correct, but these edge states were not exhaustively checked.

## C. Background refresh after final dedup/fallback code

Re-validate after at least one full 5-minute interval with no Dashboard open:

- Ceros/Joining still refreshes;
- Organia/Bernices/Estes refresh after host changes;
- exact observer-set dedup produces one private-refresh job per identical access set;
- local user #2 still sees shared data correctly despite dedup;
- Chanda dead/sentinel accounts no longer get false “not a player” skips when canonical username proves membership;
- one failing Planets.nu request does not abort other games.

## D. Communications

Validate across at least two games/accounts:

- General vs direct vs Activity classification;
- private counterpart grouping;
- root newest-first;
- replies chronological and indented;
- reload preserves selected conversation;
- same upstream activity IDs from different collections/games do not collide;
- no message from another game leaks into the selected game.

## E. Explosion / host events

Validate map + event panel for:

- Long Range Sensor named explosion;
- mine-hit destruction without VCR;
- no fake ship ID/owner inference;
- event persists historically without becoming a current ship observation.

## F. VCR visual replay

Runtime-check with real carrier battles:

- torpedo animation visible;
- individual fighters visible;
- dogfight / fighter losses visible;
- beams killing fighters visible;
- fighter attacks visible in a battle where fighters actually reach target;
- large ship sprites no longer overlap excessively;
- visual replay terminal result exactly matches deterministic non-visual replay.

## G. Battle Simulator

Validate in browser:

- arbitrary manual hull + arbitrary race;
- current known ship import;
- VCR-only Rush import in Chanda;
- two Gorbies on opposite sides where Galactic Power is off;
- Galactic Power invalid-right-side handling;
- right-carrier balance Auto / Force / Off;
- Federation +3 bays and required Fed behavior;
- required Lizard behavior including planet combat;
- optional Fury beam recharge / Privateer crew kill switches;
- adaptive weapon fields;
- repeated 10k runs and average terminal values;
- ship queue vs ship queue;
- ship queue vs planet;
- starbase carry-over fails closed after unsupported hull-damage transition rather than silently guessing.

## H. Map

Validate:

- Tesmond <-> Saratoga link appears despite 84.2 ly center distance because target warp well is W9-reachable;
- no false links are introduced by simply treating every <=84 ly pair as reachable;
- selected planet owner text is `Race / slot / username` everywhere relevant.

## I. Artwork

Hull artwork issue is not considered fully closed. Re-test problematic hull #94 against current resilient downloader. The old runtime had hull #69 success and #94 timeouts.

---

# 13. Known limitations / deliberate fail-closed behavior

- Time Machine is not yet a full historical reconstruction of every dashboard/map state.
- Starbase multi-wave state after hull damage is unsupported until the exact Host formula for base defense/tech degradation is reconstructed.
- VCR combat-time ammo/fighters are not current loadout.
- A long-range explosion report does not identify ship ID or owner unless another factual source does.
- Historical/current advantage activation should not be backfilled from current advantage state without time-compatible evidence.
- `games/list.turnstatus` is the preferred operational turn-state rail source; fallback data must not manufacture status.
- profile images are optional presentation metadata and must never block account/game access.

---

# 14. Global next directions

After the explicit validation list above, larger roadmap items remain:

1. Full historical Time Machine state reconstruction.
2. Exact Host starbase post-damage transition reconstruction for multi-wave combat.
3. More complete race/advantage resolution from game-specific historical rules rather than manual switches where time-compatible evidence exists.
4. Movement fuel model.
5. Tow resolution and unified movement-phase prediction.
6. More complete order drafting for missions/cargo/planet/starbase.
7. Explicit reviewed Planets.nu write adapter / turn submission with post-host reconciliation.
8. Continue intelligence inference without violating fact/inference boundaries.
9. Continue artwork/cache resilience where Planets.nu asset endpoints are unreliable.

---

# 15. Exact first actions for the next chat

1. Read:
   - `docs/architecture/NEW_CHAT_START.md`
   - `docs/architecture/PROJECT_STATE.md`
   - `docs/architecture/CURRENT_HANDOFF.md`
   - this file: `docs/handoff/2026-08-19-operational-ui-chat-handoff.md`
2. Inspect actual `feature/operational-ui` HEAD.
3. Inspect `/opt/planets-intel` branch/HEAD/dirty/divergence and Docker health.
4. Do **not** start a new feature immediately.
5. First run the highest-value runtime checks from section 12, especially:
   - game chooser turn-state rail / avatar / 20+ slots;
   - backend background refresh after a full interval;
   - Chanda VCR-only Rush source in Battle Simulator;
   - real VCR fighter/torpedo/beam visualization.
6. Only after those checks, pick the next global roadmap item.

## Suggested new-chat prompt

```text
Работаем с Numillyash/planets-intel. GitHub — единственный source of truth по состоянию кода.

Открой branch feature/operational-ui и сначала полностью прочитай:
1) docs/architecture/NEW_CHAT_START.md
2) docs/architecture/PROJECT_STATE.md
3) docs/architecture/CURRENT_HANDOFF.md
4) docs/handoff/2026-08-19-operational-ui-chat-handoff.md

После этого проверь фактический HEAD ветки и состояние сервера /opt/planets-intel: branch, HEAD, divergence, dirty tree, docker compose ps и /api/health.

Не восстанавливай состояние проекта из старого чата и не начинай новую фичу до проверки раздела “Things that still need runtime testing / verification” в handoff.

Сначала кратко отчитай:
- GitHub HEAD;
- server HEAD/divergence;
- health;
- какие проверки из handoff уже можно считать подтвержденными текущим runtime;
- какие остаются первыми.

Затем продолжай с Immediate next actions из CURRENT_HANDOFF.md, сохраняя инварианты: known zero != unknown, fact != inference != simulation, combat-time fact != current fact, unknown Host behavior = fail-closed.
```
