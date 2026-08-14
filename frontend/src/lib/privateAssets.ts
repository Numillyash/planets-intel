function positiveImageId(value: unknown): number | null {
    if (typeof value === "number" && Number.isInteger(value) && value > 0) {
        return value;
    }
    if (typeof value !== "string") return null;

    const trimmed = value.trim();
    const match = trimmed.match(/(?:^|\/)(\d+)(?:\.png)?(?:$|\?)/i);
    if (match === null) return null;

    const parsed = Number(match[1]);
    return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
}

export function privateHullArtworkId(
    hullId: number | null,
    payload?: Record<string, unknown> | null,
): number | null {
    // A factual ship's hull_id is the canonical identity. Some ship payloads
    // contain image-like fields that are not guaranteed to be hull artwork
    // identifiers, so using them first can display another hull entirely.
    const canonicalHullId = positiveImageId(hullId);
    if (canonicalHullId !== null) return canonicalHullId;

    // Only fall back to payload artwork hints when the observation genuinely
    // lacks a hull id. The backend resolver can still map a valid hull id to a
    // different Nu artwork id through GameRuleCatalog after a direct 404.
    if (payload !== undefined && payload !== null) {
        for (const key of ["img", "imageid", "image_id", "image"]) {
            const candidate = positiveImageId(payload[key]);
            if (candidate !== null) return candidate;
        }
    }
    return null;
}

export function privateHullAssetUrl(
    hullId: number | null,
    payload?: Record<string, unknown> | null,
): string | null {
    const imageId = privateHullArtworkId(hullId, payload);
    if (imageId === null) return null;
    return `/api/private-assets/hulls/${imageId}.png`;
}

export function privatePlanetAssetUrl(): string {
    return "/api/private-assets/planets/unknown.png";
}
