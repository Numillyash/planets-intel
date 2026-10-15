"""Field-level Planets.nu observation projection for opt-in intelligence scopes.

Pure classification only. No private peer read authorization is granted here.
Never project arbitrary `loadturn` dictionaries or user credentials. Client
controlled allowlists are not accepted; allowed keys live solely on the server.
"""
from typing import Any

from app.services.payload_safety import sanitize_observation_payload

# Keys use the exact lower-case API payload spelling where known.
# Unknown upstream fields are deliberately dropped until reviewed.
COMMON_POSITION = frozenset({
    "id", "ownerid", "x", "y", "infoturn", "name",
})
PLANET_DETAILS = frozenset({
    "temp", "clans", "nativeclans", "nativeracename", "nativegovernment",
    "nativegovernmentname", "nativehappypoints", "happypoints",
    "nativegrowth", "clanfactories", "factories", "mines", "defense",
    "defenseposts", "tax", "nativetax", "clantax", "grounddefense",
    "neutronium", "duranium", "tritanium", "molybdenum",
    "neutroniumdensity", "duraniumdensity", "tritaniumdensity",
    "molybdenumdensity", "megacredits", "supplies", "colonisttaxrate",
    "nativetaxrate",
})
SHIP_DETAILS = frozenset({
    "hullid", "engineid", "beamid", "beams", "torpedoid", "tubes", "bays",
    "ammo", "fighters", "torpedoes", "damage", "crew", "mass", "iscloaked",
    "cloaked", "experience", "warp",
})
CARGO_AND_FUNDS = frozenset({
    "megacredits", "neutronium", "duranium", "tritanium", "molybdenum",
    "supplies", "clans", "cargo", "fuel",
})
SHIP_ORDERS = frozenset({
    "warp", "mission", "missionname", "mission1target", "mission2target",
    "primaryenemy", "targetx", "targety", "targetid", "waypointx",
    "waypointy", "towtargetid", "intercepttargetid",
})
SHIP_TRANSFERS = frozenset({
    "transferammo", "transferclans", "transfermegacredits",
    "transferneutronium", "transferduranium", "transfertritanium",
    "transfermolybdenum", "transfersupplies", "transfertarget",
    "beamtransfer", "beamtransfers",
})
PLANET_BUILD_GOALS = frozenset({
    "buildgoal", "buildgoals", "targetmines", "targetfactories",
    "targetdefense", "happiness", "happinesschange", "nativehappiness",
    "nativehappinesschange",
})
STARBASE_ORDERS_INVENTORY = frozenset({
    "buildship", "buildhullid", "buildengineid", "buildbeamid",
    "buildtorpedoid", "mission", "primaryorder", "fixshipid",
    "recycleshipid", "hullinventory", "engineinventory",
    "beaminventory", "torpedoinventory", "hulls", "engines",
    "beams", "torpedoes", "shiptechlevel", "enginetechlevel",
    "beamtechlevel", "torpedotechlevel",
})
FRIENDLY_CODES = frozenset({"friendlycode", "friendly_code", "fcode"})

# Each scope adds a known family of fields; it never silently includes the
# next category (especially codes, orders, messages and credentials).
FIELD_SCOPE_MAP: dict[str, dict[str, frozenset[str]]] = {
    "planet": {
        "owned_unit_locations": COMMON_POSITION,
        "owned_planet_details": PLANET_DETAILS - CARGO_AND_FUNDS,
        "financial_and_cargo": CARGO_AND_FUNDS,
        "planet_build_goals": PLANET_BUILD_GOALS,
        "planet_friendly_codes": FRIENDLY_CODES,
    },
    "ship": {
        "owned_unit_locations": COMMON_POSITION,
        "owned_ship_details": SHIP_DETAILS - CARGO_AND_FUNDS - SHIP_ORDERS,
        "financial_and_cargo": CARGO_AND_FUNDS,
        "ship_orders": SHIP_ORDERS,
        "ship_transfers": SHIP_TRANSFERS,
        "ship_friendly_codes": FRIENDLY_CODES,
    },
    "starbase": {
        "starbase_orders_inventory": STARBASE_ORDERS_INVENTORY,
    },
}

# No generic catchall category exists. Historical rows, combat and messages
# need independent source-aware APIs with explicit turn/recipient gating.
NON_ENTITY_SCOPES = frozenset({
    "third_party_contacts", "combat_vcr_evidence", "ship_history",
    "wormhole_scans", "private_messages",
})


def project_owned_entity_fields(
    *,
    kind: str,
    raw: dict[str, Any],
    scopes: frozenset[str],
    owner_slot_id: int | None,
    grantor_slot_id: int,
) -> dict[str, Any]:
    """Project one grantor-owned object with a strict server-side field whitelist.

    Foreign objects and unclassified field types return no data. Always retain
    the native observer-specific view separately; never use this function to
    mutate it or a factual database row.
    """
    if owner_slot_id is None or owner_slot_id != grantor_slot_id:
        return {}
    categories = FIELD_SCOPE_MAP.get(kind)
    if categories is None:
        return {}
    allow = frozenset().union(*(
        keys for scope, keys in categories.items() if scope in scopes
    ))
    projected = {
        str(key): value
        for key, value in raw.items()
        if str(key).casefold() in allow
        and (value is None or isinstance(value, (str, int, float, bool)))
    }
    safe = sanitize_observation_payload(projected)
    return safe if isinstance(safe, dict) else {}


def project_private_message(
    *,
    message_id: int | None,
    message_turn: int | None,
    owner_id: int | None,
    target_id: int | None,
    headline: str | None,
    body: str | None,
    scopes: frozenset[str],
) -> dict[str, Any] | None:
    """Explicit message opt-in; never included by other categories."""
    if "private_messages" not in scopes:
        return None
    if message_id is None or message_turn is None:
        return None
    return {
        "message_id": message_id,
        "message_turn": message_turn,
        "owner_id": owner_id,
        "target_id": target_id,
        "headline": headline,
        "body": body,
    }
