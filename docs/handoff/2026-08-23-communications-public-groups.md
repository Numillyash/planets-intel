# Communications — verified Public Board + grouped private recipients — 2026-08-23

Runtime feedback after the first message-write deployment established two separate facts:

1. a private message to one recipient renders correctly as a direct conversation;
2. a private message to multiple recipients was accepted by Planets.nu but IntelBoard rendered the outgoing activity in General because the activity root did not expose one reconstructable target;
3. an official-client Network capture proved that Public Board posting uses the same `POST /game/sendmessage` endpoint as private messaging, but **omits the `to` form field entirely**.

The captured Public Board activity record was factual `activitytype=1`, `scope=2`, `targetid=<game id>`, `targettype=2`.

## Implemented

### Verified Public Board write

`PlanetsNuClient.send_message(...)` now has two explicit wire shapes:

- Public Board: `gameid`, `playerid`, `apikey`, `body`; no `to` key is present;
- Private: the same fields plus `to=slot[,slot…]`.

Both remain single-attempt writes: proxy-to-direct fallback is disabled and a transport failure is surfaced as ambiguous delivery rather than automatically retried.

The API request schema now permits an empty recipient list only as the explicit Public Board mode. The frontend exposes Public Board as a real send option rather than a disabled placeholder.

Post-send Public Board reconciliation is deliberately strict. A new outgoing activity must match sender and body and also match the captured public shape:

- `target_id == game_id`;
- `target_type == 2`;
- `scope == 2`.

This prevents a private message with the same text from being mistaken for confirmation of a public post.

### Grouped private messages

Endpoint provenance alone did not solve outgoing multi-recipient messages reliably. IntelBoard itself has a stronger factual source for messages it sends: the explicit recipient slot set accepted by the user before the write.

Revision `0017_outgoing_msg_recipients` adds nullable JSON field:

`game_activity_observations.outgoing_recipient_player_ids`

After a successful private send and successful observation of the new outgoing activity id, IntelBoard marks that activity with:

- `visibility_source = outgoing_private_write`;
- the exact deduplicated/sorted recipient player-slot ids.

This metadata is sticky across later activity-feed upserts.

Read-side semantics now treats `outgoing_private_write` as factual private provenance. It exposes `conversation_player_ids` and, when the current canonical roster resolves every slot, derives a display label such as:

`helping die + mussoleni ii`

The frontend keys these conversations by the sorted recipient slot set, for example:

`private:slots:5,7`

Replying to that group restores the same factual recipient selection.

### Historical limitation

Messages sent before this recipient-set provenance existed cannot safely be retroactively assigned a recipient group unless Planets.nu itself still exposes enough private evidence. Do not infer old group membership from message text or broad activity shape alone.

A newly sent multi-recipient private message after this deployment is the correct runtime validation case.

## Regression coverage

Added/updated tests cover:

- Public Board schema accepts zero recipients;
- zero recipients are validated as explicit public mode;
- official Public Board wire format omits `to` entirely;
- private wire format sends comma-separated `to`;
- legacy message text escaping remains intact;
- Public Board reconciliation requires the captured game-target/scope shape;
- multi-recipient private reconciliation marks the observed activity with its exact recipient set;
- Public Board sends never receive private-write metadata;
- outgoing group provenance makes an activity private even when its raw activity shape is otherwise public-like;
- replies inherit the root's outgoing recipient group.

## Deployment gate

This patch adds migration `0017_outgoing_msg_recipients` on top of `0016_activity_provenance`.

Do not restart the new backend against an unmigrated database.

```bash
cd /opt/planets-intel

git fetch origin
git checkout feature/operational-ui
git pull --ff-only origin feature/operational-ui

git rev-parse HEAD

docker compose build backend

docker compose run --rm \
  -v "$PWD/backend/tests:/app/tests:ro" \
  backend \
  python -m unittest discover -s /app/tests -p 'test_*.py' -v

# Only after the suite ends in OK:
docker compose run --rm backend alembic upgrade head
docker compose up -d backend

curl -fsS http://127.0.0.1:18080/api/health
echo
```

## Runtime validation

After deploy and Ctrl+F5:

1. send one harmless Public Board post; confirm it appears once in Planets.nu and in IntelBoard General;
2. send one harmless private message to one recipient; confirm the existing direct conversation behavior remains correct;
3. send one harmless private message to two recipients; confirm IntelBoard creates one distinct Direct Messages group labelled from both recipient names rather than placing it in General;
4. press Reply inside that group and confirm both recipients are preselected;
5. do not intentionally induce transport failure during a live write.
