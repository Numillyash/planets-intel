# Communications provenance + composer follow-up — 2026-08-23

User runtime feedback after the first real message write:

- the composer textarea used the browser's white default and was visually disruptive;
- there was no safe Public Board/general-chat write path in IntelBoard;
- a real private message sent to two recipients arrived in Planets.nu, but IntelBoard rendered it in General instead of Direct Messages.

The test message was visibly marked by Planets.nu as a private message with two recipients. That exposed a read-side provenance bug rather than a delivery failure.

## Implemented

### Dark composer

`CommunicationsPanel` now uses a dedicated dark textarea style and an explicit delivery-mode control. The textarea has dark background, light text, themed placeholder/focus/disabled states and remains vertically resizable.

### Private-message classification now preserves factual endpoint provenance

Before this change, `sync_private_game()` fetched both:

- `account/ingameactivity`;
- `account/privateactivity`.

It then merged both lists before persistence. `GameActivityObservation` therefore lost the crucial fact of **which upstream endpoint exposed the record**. Read-side classification consequently relied on raw `scope`/`targetid` shape. That is unsafe for a private message with multiple recipients because one activity root may have no single target id.

Revision `0016_activity_provenance` adds nullable `game_activity_observations.visibility_source`.

Current sync persists the feeds separately:

- `ingame_activity` for records observed through the broad in-game activity endpoint;
- `private_activity` for records observed through the dedicated private-activity endpoint.

`private_activity` provenance is sticky during upsert: a later copy from the broad feed cannot downgrade an activity already proven private.

Read-side message semantics now classify an activity-type-1 record as private when the row or its thread root has factual `private_activity` provenance. `scope == 3` remains only as a compatibility fallback for historical rows written before provenance existed.

This preserves the invariant `fact != inference`: the UI no longer needs one target id in order to know that an activity came from the private feed.

For multi-recipient private messages where Planets.nu does not expose one factual conversation partner, IntelBoard displays a neutral `Private thread` rather than inventing a player name.

### Existing records

The migration does **not** fabricate endpoint provenance for pre-existing rows. Historical records receive `visibility_source = NULL`, because their stored raw shape cannot prove which endpoint originally exposed them.

Legacy `scope == 3` remains a read-side compatibility fallback only; it is not rewritten into factual `private_activity` provenance.

After deployment, the next private refresh should re-upsert still-visible private activity with its actual endpoint provenance. The already-sent runtime test message should therefore leave General if it is returned by `account/privateactivity`, without being sent again.

## Public Board write remains fail-closed

The existing write endpoint wraps Planets.nu `game/sendmessage`, which is the direct/private message path. Public Board posting is a separate upstream mechanism. The exact current Public Board write payload has not yet been verified from an authoritative request capture.

IntelBoard therefore now makes the distinction visible in the composer but keeps `Public Board` sending disabled. It does **not** guess that an empty recipient list means a public post.

To finish Public Board sending, capture one harmless Public Board post from the official Planets.nu client in browser DevTools Network, preserving the request field names/shape while redacting the API key value. Then reproduce only that proven payload with the existing single-attempt/ambiguous-write safety model.

## Source-level coverage

Tests now cover:

- direct-message schema rejects zero recipients;
- empty recipient list cannot accidentally invoke a guessed Public Board transport;
- dedicated private-feed provenance classifies a targetless record as private even when raw scope shape alone would not;
- replies inherit factual private provenance from their root;
- legacy `scope = 3` rows remain private;
- broad in-game activity without private evidence remains General;
- existing direct-message reconciliation and ambiguous-write behavior remain covered.

## Required deployment order

This change includes a database migration. Do not restart the new backend image against the old schema.

```bash
cd /opt/planets-intel
git fetch origin
git checkout feature/operational-ui
git pull --ff-only origin feature/operational-ui

docker compose build backend
docker compose run --rm backend alembic upgrade head
docker compose up -d backend

curl -fsS http://127.0.0.1:18080/api/health
echo
```

Then reload Communications and allow/trigger a normal private-intel refresh before evaluating the old multi-recipient test message classification.
