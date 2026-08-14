const PRIVATE_ARTWORK_VERSION = 5;
const NU_HULL_ARTWORK_BASE_URL = "https://mobile.planets.nu/img/hulls";

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

function payloadHullArtworkHint(
    payload?: Record<string, unknown> | null,
): number | null {
    if (payload === undefined || payload === null) return null;
    for (const key of ["img", "imageid", "image_id", "image"]) {
        const candidate = positiveImageId(payload[key]);
        if (candidate !== null) {
            return normalizedNuHullArtworkId(candidate);
        }
    }
    return null;
}

export function privateHullArtworkId(
    hullId: number | null,
    payload?: Record<string, unknown> | null,
): number | null {
    const canonicalHullId = positiveImageId(hullId);
    if (canonicalHullId !== null) {
        return normalizedNuHullArtworkId(canonicalHullId);
    }
    return payloadHullArtworkHint(payload);
}

export function privateHullAssetUrl(
    hullId: number | null,
    payload?: Record<string, unknown> | null,
): string | null {
    const imageId = privateHullArtworkId(hullId, payload);
    if (imageId === null) return null;

    // Hull artwork is intentionally loaded from the canonical Nu asset URL.
    // The browser can reach these public static assets reliably, while the
    // server-side cache may be blocked or throttled by the asset host. Using
    // the original PNG also preserves the exact geometry used by Planets.nu
    // instead of applying server-side crop/centroid transformations.
    return `${NU_HULL_ARTWORK_BASE_URL}/${imageId}.png`;
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
