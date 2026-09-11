# Private refresh failure safety — 2026-09-11

This checkpoint hardens the IntelBoard live-map refresh path after the production proxy incident recorded on 2026-09-10.

## Incident pattern

The accessible private-refresh endpoint deliberately returns per-observer status in a successful HTTP 200 response. Before this change the frontend called the endpoint and discarded that response body. If every eligible private observer failed while an older factual snapshot still existed locally, the map could continue rendering stale private intel without surfacing the per-account synchronization failure.

This was observed during the stale proxy incident: canonical/public game state advanced while private loadturn synchronization failed for the accessible accounts.

## Change

`frontend/src/api/client.ts` now models the accessible-refresh response and fails the auto-refresh call when all eligible observers failed and the response contains no refreshed or accepted cached result.

The error message preserves the server-supplied per-observer diagnostic text and Planets.nu username. `PrivateIntelMap` already catches refresh errors and renders them as a live `Refresh warning`, so no map component behavior change is required for this first bounded safety fix.

Partial success is intentionally not turned into an exception in this change: a successful observer refresh must still allow the caller to reload the usable private/combined snapshot. A later freshness/provenance improvement can expose per-source partial staleness without blocking successful refreshes.

## Scope

This change does not alter factual observation persistence, sharing semantics, refresh throttling, or historical backfill. It only prevents the catastrophic all-observers-failed HTTP-200 case from being silently treated as successful by the frontend.

Deployment/runtime acceptance remains separate from CI and must not be inferred from the merge alone.
