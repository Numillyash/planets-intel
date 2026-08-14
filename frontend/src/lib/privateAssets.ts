const PRIVATE_ARTWORK_VERSION = 2;

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

function normalizedNuHullArtworkId(hullId: number): number {
    if (hullId > 1000 && hullId < 4000) {
        const normalized = hullId % 1000;
        if (normalized > 0) return normalized;
    }
    return hullId;
}

function safePlanetArtworkName(value: unknown): string | null {
    if (typeof value === "number" && Number.isInteger(value) && value >= 0) {
        return String(value);
    }
    if (typeof value !== "string") return null;

    const trimmed = value.trim();
    if (!trimmed) return null;

    const match = trimmed.match(/(?:^|\/)([A-Za-z0-9_-]+)(?:\.png)?(?:$|\?)/);
    return match?.[1] ?? null;
}

export function privateHullArtworkId(
    hullId: number | null,
    payload?: Record<string, unknown> | null,
): number | null {
    const canonicalHullId = positiveImageId(hullId);
    if (canonicalHullId !== null) {
        return normalizedNuHullArtworkId(canonicalHullId);
    }

    if (payload !== undefined && payload !== null) {
        for (const key of ["img", "imageid", "image_id", "image"]) {
            const candidate = positiveImageId(payload[key]);
            if (candidate !== null) {
                return normalizedNuHullArtworkId(candidate);
            }
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
    return `/api/private-assets/hulls/${imageId}.png?v=${PRIVATE_ARTWORK_VERSION}`;
}

export function privatePlanetArtworkName(
    payload?: Record<string, unknown> | null,
): string | null {
    if (payload !== undefined && payload !== null) {
        for (const key of ["img", "image", "imageid", "image_id"]) {
            const candidate = safePlanetArtworkName(payload[key]);
            if (candidate !== null) return candidate;
        }
    }
    return null;
}

export function privatePlanetAssetUrl(
    payload?: Record<string, unknown> | null,
): string {
    const artwork = privatePlanetArtworkName(payload) ?? "unknown";
    return `/api/private-assets/planets/${encodeURIComponent(artwork)}.png?v=${PRIVATE_ARTWORK_VERSION}`;
}
