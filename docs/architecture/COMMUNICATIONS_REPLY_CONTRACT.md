# Communications — verified Planets.nu game reply contract

Verified from the public Planets.nu 1.24 client on 2026-08-25:

```text
https://mobile.planets.nu/1.24/nu.js
```

This document records wire behavior only. It is not an inference about Host behavior.

## Game-feed write endpoint

The official game client implements:

```javascript
postGameMessage: function(body, parentid, to) {
    ...
    data.add("gameid", this.gameId);
    data.add("playerid", this.player.id);
    data.add("apikey", vgap.apikey);
    if (to) data.add("to", to);
    if (parentid) data.add("parentid", parentid);
    data.add("body", body);
    this.request("/game/sendmessage", data, ...);
}
```

Therefore:

| Operation | `to` | `parentid` |
| --- | --- | --- |
| Public root message | omitted | omitted |
| Private root message | `slot[,slot…]` | omitted |
| Public reply | omitted | root activity id |
| Private reply | exact other participant slots | root activity id |

A game-feed reply does **not** require a different endpoint. It uses the same
`/game/sendmessage` endpoint as a root message.

## Reply-to-reply semantics

The Planets.nu activity model renders replies from root `_replies` and the game
feed exposes the Reply action on the root activity. IntelBoard may offer Reply on
a displayed child for convenience, but upstream `parentid` must still be the
factual `thread_root_id`, not the child activity id.

Example captured during runtime verification:

```text
root:  activity_id=7634370
child: activity_id=7634954, parent_id=7634370
```

Clicking Reply on either item must therefore produce:

```text
parentid=7634370
```

## Read contract

The public client also confirms:

- `/account/privateactivity` provides private activity and `_replies`;
- `scope == 3` marks private messages;
- `targettype == 4` marks group private messages;
- `/account/thread` loads a thread using `activityid=<root id>`.

## IntelBoard safety rules

IntelBoard write behavior must remain fail-closed:

1. Frontend sends the factual activity id on which the user clicked Reply.
2. Backend resolves that observation to its stored `thread_root_id`.
3. Private replies require the exact factual participant slot set for the observer.
4. Changing compose mode or recipients cancels reply semantics.
5. Post-send reconciliation for a reply requires the newly observed activity to
   have `parent_id == expected thread root id`.
6. A new root with identical text must never satisfy reply reconciliation.
7. Transport-level write failures remain ambiguous and must never be retried
   automatically, because doing so can duplicate the user action.

This contract is covered by `backend/tests/test_communication_reply.py`.
