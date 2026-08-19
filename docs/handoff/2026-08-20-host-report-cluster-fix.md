# Host report clustering fix — 2026-08-20

Runtime feedback on Chanda M Sector T19 clarified that the overlapping `Explosion · ...` markers were not duplicate VCRs. They were two distinct factual long-range explosion reports at the same coordinates, and no VCR existed for those incidents.

## Changes

- Removed presentation-level suppression/correlation of long-range explosion reports merely because a VCR exists at the same coordinates. VCR and host-report evidence remain independent.
- Map rendering now groups distinct unreviewed explosion reports by exact turn + coordinates.
  - one report => `Explosion · <ship name>`
  - multiple distinct reports => one `Explosions ×N` marker
- Distinct ship names at the same position are preserved as separate factual reports in `Reports`; clustering is presentation-only.
- Clicking an explosion cluster marks each member report as reviewed for the local browser and removes the map notification. Facts/provenance remain unchanged in Reports/database.
- Host-report review state persists in browser localStorage per game + turn.
- The fullscreen Intelligence -> Reports pane now uses the embedded/full-height HostEventPanel rather than the old compact 190px map-panel height.

## Runtime checks after deploy

1. Chanda T19 at 1873,2063 should show one `Explosions ×2` map marker rather than overlapping ILL WIND / NEBULA labels.
2. Clicking that marker should open Reports and immediately remove the map notification.
3. Both individual explosion facts must still be present in Reports.
4. Reloading the page must not restore the reviewed map marker for that game/turn.
5. Actual VCR markers at the same coordinates, if any exist in another case, remain separate and use the VCR replay popup/review state.
6. Reports should fill the Intelligence content area instead of rendering as a ~190px-high scroll strip.

No factual host-event rows, combat observations, provenance, inference, or simulator behavior were modified.
