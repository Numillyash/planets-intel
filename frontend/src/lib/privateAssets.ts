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
    if (payload !== undefined && payload !== null) {
        for (const key of ["img", "imageid", "image_id", "image"]) {
            const candidate = positiveImageId(payload[key]);
            if (candidate !== null) return candidate;
        }
    }
    return positiveImageId(hullId);
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
