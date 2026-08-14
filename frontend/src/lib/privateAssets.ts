export function privateHullAssetUrl(hullId: number | null): string | null {
    if (hullId === null || !Number.isInteger(hullId) || hullId <= 0) {
        return null;
    }
    return `/api/private-assets/hulls/${hullId}.png`;
}
