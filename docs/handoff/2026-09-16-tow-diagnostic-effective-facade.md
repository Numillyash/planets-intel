# Tow diagnostic effective-facade correction — 2026-09-16

The runtime inspector originally imported the saved-draft-only prediction facade. After factual Tow participants were added to the API through `movement_prediction_effective`, that made the diagnostic stale relative to production behavior.

The inspector is corrected to call `get_effective_movement_prediction` and to match separately emitted target rows by `tow_tower_ship_id` as well as the requested ship id / target ids.

This is diagnostic-only behavior; it does not change Host mechanics or certainty policy.
