# 2026-09-16 factual Tow runtime recheck

## Runtime checkpoint

Production was deployed at:

`ba25acb79a4f58a6d901ecf1fa449e36b370d27a`

Deployment result supplied from `/opt/planets-intel`:

- production image build: OK
- backend tests: 299 OK
- Alembic: `0018_tow_target_ship_id (head)` before/after
- backend recreate: OK
- health: `{"status":"ok","service":"planets-intel-backend"}`
- deploy log: `/opt/planets-intel/logs/deploy/20260916-164942-production.log`

The server checkout was then advanced to diagnostic/docs HEAD `ebb4b7e1feaf3ac57caae7db81e1631c1687b3d9` without redeploying; the running production image therefore remained `ba25acb...` while the read-only Tow diagnostic was executed from the checked-out host tree.

## Exact production-state diagnostic

Command:

```bash
bash scripts/maintenance/inspect-tow-orders.sh 33 79
```

Relevant current match:

- game: `684653`
- linked account: `2`
- observer slot: `2`
- turn: `29`
- batch: `148758`

### Eros #79

The latest factual private snapshot already contains the upstream Tow order:

- ship `79`, EROS CLASS RESEARCH VESSEL
- owner `2`
- factual mission `6`
- factual `mission1target=63`
- warp `8`
- origin `(2254,1861)`
- waypoint `(2252,1854)`
- neutronium snapshot `110`
- no local draft row

After the effective-prediction facade fix, movement prediction emits **both** Tow participants even though neither participant requires its own local draft row:

- tower row: `ship_id=79`, `tow_role=tower`, `tow_target_ship_id=63`
- target row: `ship_id=63`, `tow_role=target`, `tow_tower_ship_id=79`

The Tow lock is known and the pre-well endpoint is known, but the final endpoint remains correctly fail-closed because Tow + planetary warp-well interaction has not been independently verified:

- `status=locked_route_unresolved`
- `certain=false`
- `blocker_class=dependency_unresolved`
- pre-well endpoint `(2252,1854)`
- candidate warp well: planet `44`, `Gothos`
- pull distance `3.0`
- final `predicted_x/y=null`

This proves the earlier Eros issue was **not** private-ingestion loss. The factual Tow exists in persisted data and now appears in effective prediction. What remains is an unresolved Host interaction plus presentation of that uncertainty.

### Lizard Class Cruiser #33

For the same current game/account/turn, the persisted state is:

- ship `33`, LIZARD CLASS CRUISER
- factual mission `8`
- factual Tow target absent
- position `(2360,2114)`
- waypoint `(2360,2114)`
- local `ShipOrderDraft`: **absent**

Therefore the missing LCC prediction in this diagnostic cannot be attributed to the Tow renderer. At the instant of the probe there is no saved current-turn draft in the database for ship #33. A browser editor can still contain unsaved local changes, so follow-up acceptance must explicitly save the draft and immediately re-run the diagnostic before diagnosing persistence.

## Product consequence

The map currently renders only predictions with a final endpoint. For Eros this suppresses the now-correct factual Tow rows because `predicted_x/y` are intentionally null at the Tow + warp-well boundary. The next UI patch should render the known Tow/pre-well leg and visibly mark the final endpoint as unknown rather than silently hiding the factual Tow.

Evidence boundaries remain unchanged:

- known factual Tow order != known final Tow endpoint;
- a known pre-well endpoint does not prove Tow + warp-well Host ordering;
- local browser editing state != persisted `ShipOrderDraft`;
- unknown final position must remain unknown.
