# Current game: previous encounters matrix

Added 2026-10-17 to the existing Commander Intelligence surface.

This implements the user-facing matrix concept behind the historic
Whisperer / later derblondehans player-affinity-tool reference. It does **not**
reuse third-party implementation, contact external UI services, or require a
new CORS proxy. Sources are the already established IntelBoard
`GET /api/games/{game_id}/commander-intelligence`, its public history and
source-indexed reconstruction caches.

- Every row and column is an attributable human commander in the selected
  canonical game roster. The matrix excludes this game from pair counts.
- **Shared games** are the intersection of both users' public history records,
  not proven friendship or even proven temporal overlap.
- **Overlapping turns** are exact only with fully bounded historical
  participation; `≥n` denotes a known lower bound when some evidence is
  incomplete; `?` means unknown, not zero.
- Click on any off-diagonal cell for source sectors, intervals, and
  `loadinfo` provenance using the existing PairDetails component.
- Selective filter of players with prior shared games is a display-only
  transformation of the same response.
- The backend continues to use its authenticated route and cached, bounded
  public API fanout. No new private data is accessed or persisted.

Upstream historical reference:
https://github.com/derblondehans/player-affinity-tool

External code is not copied; historical association is distinct from
behavioral inference. There is no evidence-based direct "ally" label.
