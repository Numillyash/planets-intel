# 2026-09-10 — private refresh proxy incident runtime

## Scope

This handoff records a production runtime incident in which the public game state advanced normally while private intelligence remained stale. It is an operational/runtime checkpoint only; no Host-mechanics inference is made here.

GitHub remains the source of truth for code. At the start of this incident investigation, `feature/operational-ui` was at:

```text
0ff6705721ce1791e16100984e250c5ed65ece6c
```

The production server checkout remained on the previously deployed code:

```text
f3d807faef4ef763d4898f91d3b27faaa319d52e
```

The incident was caused by production environment configuration, not by a code regression between those SHAs.

## Symptom

Beta Auriga Sector was at public/canonical turn 20, while the operational map still showed positions consistent with roughly turn 16. The VCR tab also showed no VCRs for turn 20 even though the official Planets.nu client showed two VCRs for that turn.

## Scheduler diagnostic

`python -m app.scripts.inspect_background_refresh --run` confirmed that the background scheduler itself was healthy:

```text
Beta Auriga Sector
canonical turn: 20
public_sync: refreshed
```

For game `684653`, the two actual participants in the linked-account set were:

```text
linked_account_id=2  helping die   -> failed
linked_account_id=3  mussoleni ii  -> failed
```

The other linked accounts were correctly skipped as not being players in that game.

The same private-sync failure pattern affected other active games as well, while public synchronization continued to succeed.

## Root cause

Production `/opt/planets-intel/.env` still contained the obsolete proxy endpoint:

```text
PLANETSNU_PROXY_URL=http://10.147.17.166:18088
```

The working Windows/ZeroTier -> WSL Tinyproxy endpoint had changed and was independently restored/tested as:

```text
PLANETSNU_PROXY_URL=http://10.147.17.198:18088
```

A direct private sync before the fix produced the decisive error:

```text
app.planetsnu.client.PlanetsNuError:
Planets.nu request failed: proxy ConnectError; direct ReadTimeout
```

Thus:

```text
obsolete proxy endpoint
-> proxy ConnectError
-> direct fallback ReadTimeout
-> no new private loadturn snapshot persisted
-> latest private intel remained stale
-> frontend continued rendering the last successful snapshot
```

## Runtime repair

The server `.env` was changed to:

```text
PLANETSNU_API_BASE_URL=https://api.planets.nu
PLANETSNU_PROXY_URL=http://10.147.17.198:18088
```

The backend container was force-recreated and confirmed to receive the new environment value.

Two manual private-sync acceptance runs then succeeded for Beta Auriga game `684653`:

### helping die

```text
linked_account_id: 2
planets_username: helping die
turn: 20
batch_id: 123227
created: false
combat_reports: 2
ships: 20
```

### mussoleni ii

```text
linked_account_id: 3
planets_username: mussoleni ii
turn: 20
batch_id: 123228
created: false
combat_reports: 2
ships: 17
```

`created: false` is not a failure: the persistence layer deduplicates an identical `(game, turn, observer, source, snapshot_hash)` snapshot and returns the existing batch. This indicates that by the time of the explicit CLI runs the repaired background/browser refresh path had already persisted the same turn-20 snapshot.

The official Planets.nu client showed two VCRs on turn 20, matching `combat_reports: 2` from both private payloads.

The user then refreshed the IntelBoard and reported that it appeared to be working again.

## Operational conclusion

The stale-map incident is runtime-confirmed as an infrastructure/configuration failure, not a Pixi rendering defect and not a canonical-turn scheduler failure.

The working production proxy endpoint as of this checkpoint is:

```text
http://10.147.17.198:18088
```

Do not assume this endpoint from memory in future incidents; inspect the actual production `.env` and verify transport before drawing conclusions.

## Follow-up product hardening

The incident exposed two application-level observability gaps that should be addressed separately from the runtime repair:

1. The UI should explicitly mark private intel as stale when canonical game turn is newer than the displayed private snapshot turn, rather than allowing a stale map to look live.
2. Aggregate refresh diagnostics should preserve useful per-account private-sync failure detail instead of collapsing a concrete error such as `proxy ConnectError; direct ReadTimeout` into only `Planets.nu private synchronization failed`.

These are follow-up robustness tasks. The production data path itself was restored without changing application code.
