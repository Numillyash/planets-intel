# Communications write + diplomacy guard — 2026-08-21

This checkpoint starts the intelligence-first upstream write path. It deliberately covers **messages first** and keeps diplomacy writes fail-closed until the exact Planets.nu relation serializer is proven.

## Implemented

### Communications write path

- `PlanetsNuClient.send_message(...)` targets `game/sendmessage` with one explicit form POST.
- Legacy non-public text escaping is applied before the HTTP form encoder:
  - `& -> |||`
  - `= -> :::`
- A message write never performs proxy->direct fallback or any other automatic retry.
- A transport failure after the write begins is surfaced as **ambiguous delivery**, not as failure-safe-to-retry and not as success.
- The backend re-loads the current authenticated turn before sending and requires factual `canmessage` permission.
- Sender identity is checked against:
  - linked local account ownership;
  - current authenticated `rst.player`;
  - canonical game slot/account/username;
  - active human-player state.
- Recipient slots are deduplicated and must exist as active human slots in the canonical current roster.
- Successful upstream acceptance is distinct from post-send reconciliation.
- After upstream success IntelBoard performs a read-side private sync and attempts to observe a **new** outgoing activity record with matching sender/body and, when available, direct target account.
- The response exposes `upstream_accepted` and `reconciled` separately.

### Communications UI

`CommunicationsPanel` now contains an explicit composer:

- New message / Reply;
- current human roster as explicit recipients;
- multi-recipient selection;
- text preview/editing;
- browser confirmation before the write;
- the Send button is locked while the request is in flight;
- success, accepted-but-not-yet-reconciled, and error/ambiguous states are visually distinct;
- no automatic retry is offered or performed.

The UI resolves the current observer slot only for recipient convenience. The backend repeats the authoritative identity and recipient checks.

### Diplomacy read-side correction

The previous UI had the Nu relation directions reversed. It is corrected to:

- `relation_to` = **You -> them**;
- `relation_from` = **Them -> you**.

Validated named codes are now displayed while preserving the raw number:

- `-1` Blocked Communications
- `0` None
- `1` Send Ambassador
- `2` Safe Passage
- `3` Share Intel
- `4` Full Alliance

Unknown values remain explicit instead of being guessed.

## Diplomacy write remains blocked intentionally

Evidence from the Planets.nu client/plugin save path confirms that relation changes are written through `/game/save`, not through a dedicated relation endpoint. The save bundle sends every relation as:

`Relation<relation.id> = serializeRelation(relation)`

along with current game/player/turn/version/savekey/apikey/saveindex/keycount metadata.

The exact current `serializeRelation()` payload format has **not** been proven from an authoritative/current source yet. IntelBoard therefore does not expose an editable diplomacy control in this checkpoint.

Do not implement `/game/save` relation writes by guessing the serialization format. Unknown save semantics remain fail-closed.

## Source-level tests added

- read requests may proxy-fallback on transport failure;
- write requests never fallback/retry after transport failure;
- ambiguous write transport is a dedicated error;
- non-public message text escaping is explicit;
- message form fields are sent exactly once;
- post-send reconciliation requires a new outgoing activity record;
- upstream acceptance and reconciliation are independent outcomes.

## Runtime validation gate

Before using the composer for a real message:

1. production frontend/backend image must build;
2. full backend unit suite must pass;
3. `/api/health` must remain OK after deploy;
4. verify Communications shows New message / Reply and the correct current roster;
5. send **one harmless user-authored message to one known recipient**;
6. verify the confirmation dialog before sending;
7. verify the message appears once in Planets.nu and IntelBoard;
8. verify IntelBoard reports whether the refreshed feed reconciled it;
9. only after the basic send is proven, test a harmless message containing `&` and `=` if desired.

Do not intentionally induce a network failure during a live write merely to test ambiguous delivery; that behavior is covered by unit tests.

## Next step

After message runtime validation, recover the exact current relation serialization. Preferred order:

1. continue source recovery if possible;
2. otherwise capture the request payload for one harmless diplomacy change in the official Planets.nu client using browser DevTools Network;
3. reproduce only the proven relation bundle format;
4. add single-attempt `/game/save` write transport, explicit confirmation, and post-write loadturn reconciliation before exposing editable diplomacy.
