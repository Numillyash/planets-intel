from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Mapping

from app.scripts.combat_corpus_coverage import run as run_coverage


def _compact(report: Mapping[str, Any]) -> dict[str, Any]:
    mechanics = report.get("mechanics")
    races = report.get("races")

    mechanic_counts: dict[str, int] = {}
    if isinstance(mechanics, Mapping):
        for name, row in mechanics.items():
            if not isinstance(row, Mapping):
                continue
            count = row.get("count")
            if isinstance(count, int) and not isinstance(count, bool):
                mechanic_counts[str(name)] = count

    race_counts: dict[str, dict[str, int]] = {}
    if isinstance(races, Mapping):
        for race_id, row in races.items():
            if not isinstance(row, Mapping):
                continue
            compact_row: dict[str, int] = {}
            for key in (
                "ship_side_appearances",
                "ship_battles",
                "carrier_side_appearances",
                "planet_side_appearances",
            ):
                value = row.get(key)
                if isinstance(value, int) and not isinstance(value, bool):
                    compact_row[key] = value
            race_counts[str(race_id)] = compact_row

    return {
        "diagnostic": "combat_corpus_summary",
        "read_only": True,
        "filters": report.get("filters"),
        "summary": report.get("summary"),
        "battle_shapes": report.get("battle_shapes"),
        "mechanic_counts": mechanic_counts,
        "race_counts": race_counts,
        "notes": [
            "This is a compact projection of combat_corpus_coverage; it introduces no new combat classification rules.",
            "Counts show factual VCR input coverage only, not proof that a Host special rule fired or is implemented correctly.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compact read-only summary of factual combat VCR corpus coverage."
    )
    parser.add_argument(
        "--game-id",
        type=int,
        default=None,
        help="Restrict the summary to one game. Default: all games with stored VCRs.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    coverage_args = argparse.Namespace(game_id=args.game_id)
    json.dump(
        _compact(run_coverage(coverage_args)),
        sys.stdout,
        ensure_ascii=False,
        indent=2,
        default=str,
    )
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
