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
    // Nu campaign/upgraded hull ids commonly reuse the base hull artwork.
    // The classic client strips the 1000/2000/3000 namespace before building
    // /img/hulls/<id>.png. Keep genuinely new 1..999 artwork ids untouched.
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
    // A factual ship's hull_id is the canonical identity. Some ship payloads
    // contain image-like fields that are not guaranteed to be hull artwork
    // identifiers, so using them first can display another hull entirely.
    const canonicalHullId = positiveImageId(hullId);
    if (canonicalHullId !== null) {
        return normalizedNuHullArtworkId(canonicalHullId);
    }

    // Only fall back to payload artwork hints when the observation genuinely
    // lacks a hull id. The backend resolver can still map a valid hull id to a
    // different Nu artwork id through GameRuleCatalog after a direct 404.
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
    return `/api/private-assets/hulls/${imageId}.png`;
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
    return `/api/private-assets/planets/${encodeURIComponent(artwork)}.png`;
}
