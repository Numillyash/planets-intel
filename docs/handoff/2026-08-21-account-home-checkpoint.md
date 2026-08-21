# Account home checkpoint — 2026-08-21

## Scope

Account management is now global instead of game-specific.

- `/intelboard` remains the canonical shared home.
- `AccountSettings` is rendered on that home as a collapsible section.
- Link/unlink refreshes the picker account/game state.
- The per-game Dashboard no longer exposes an Accounts button or a separate AccountSettings page.
- If a stale game URL is opened with no active linked observers, the game surface points the user back to `/intelboard`.

## Validation required

This change is source-reviewed but not yet runtime-validated.

After deploy verify:

1. `/intelboard` shows Account settings and the two observer columns.
2. Linking/unlinking updates the home without requiring navigation into a game.
3. Per-game Dashboard top-right area has no Accounts button.
4. Existing Games / Dashboard / Intel / Starmap SPA routing is unchanged.
5. Full production frontend build and backend test suite pass.
