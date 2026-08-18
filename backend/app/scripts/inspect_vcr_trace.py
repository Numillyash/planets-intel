import argparse
import json
from collections import Counter
from typing import Any

from app.services.combat_replay_trace import _load_replay_context
from app.services.vcr_replay_nu import replay_nuhost_from_nu_catalog
from app.services.vcr_replay_trace import replay_nuhost_trace


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare one stored VCR's visual trace against the deterministic "
            "non-visual replay and summarize emitted visual event kinds."
        )
    )
    parser.add_argument("user_id", type=int)
    parser.add_argument("game_id", type=int)
    parser.add_argument("linked_account_id", type=int)
    parser.add_argument("turn", type=int)
    parser.add_argument("vcr_id", type=int)
    return parser.parse_args()


def _terminal_from_trace(trace: dict[str, Any]) -> dict[str, Any] | None:
    frames = trace.get("frames")
    if not isinstance(frames, list) or not frames:
        return None
    final = frames[-1]
    if not isinstance(final, dict):
        return None
    return final


def _terminal_projection(side: object) -> dict[str, object] | None:
    if not isinstance(side, dict):
        return None
    return {
        key: side.get(key)
        for key in ("shield", "damage", "crew", "torpedoes", "fighters")
    }


def main() -> None:
    args = parse_args()
    context = _load_replay_context(
        user_id=args.user_id,
        game_id=args.game_id,
        linked_account_id=args.linked_account_id,
        turn=args.turn,
        vcr_id=args.vcr_id,
    )
    if context is None:
        raise SystemExit("accessible VCR replay context not found")

    payload, beams, torpedoes, settings, _hulls = context
    plain = replay_nuhost_from_nu_catalog(
        payload,
        beams=beams,
        torpedoes=torpedoes,
        settings=settings,
    )
    traced = replay_nuhost_trace(
        payload,
        beams=beams,
        torpedoes=torpedoes,
        settings=settings,
    )
    final = _terminal_from_trace(traced)

    effect_counts: Counter[str] = Counter()
    frames = traced.get("frames")
    if isinstance(frames, list):
        for frame in frames:
            if not isinstance(frame, dict):
                continue
            effects = frame.get("effects")
            if not isinstance(effects, list):
                continue
            for effect in effects:
                if isinstance(effect, dict) and isinstance(effect.get("kind"), str):
                    effect_counts[effect["kind"]] += 1

    terminal_matches = final is not None and all(
        _terminal_projection(final.get(side_name))
        == _terminal_projection(plain.get(side_name))
        for side_name in ("left", "right")
    )
    result_matches = traced.get("result") == plain.get("result")
    cycles_match = traced.get("cycles") == plain.get("cycles")

    report = {
        "game_id": args.game_id,
        "turn": args.turn,
        "vcr_id": args.vcr_id,
        "result_matches": result_matches,
        "cycles_match": cycles_match,
        "terminal_matches": terminal_matches,
        "deterministic_match": result_matches and cycles_match and terminal_matches,
        "plain_result": plain.get("result"),
        "trace_result": traced.get("result"),
        "plain_cycles": plain.get("cycles"),
        "trace_cycles": traced.get("cycles"),
        "effect_counts": dict(sorted(effect_counts.items())),
    }
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))

    if not report["deterministic_match"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
