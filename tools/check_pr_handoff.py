#!/usr/bin/env python3
"""Enforce durable documentation and a copy-ready chat continuation on EVERY PR.

The check runs against the exact PR base/head file diff, not GitHub event text,
not a model's memory, and not the prior chat. PRs on other branches are out
of scope; main/runtime-logs direct pushes are unaffected.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

CONTINUATION = "docs/CONTINUE_HERE.md"
CHANGELOG = "docs/PR_CHANGELOG.md"
CORE_DOCUMENTS = frozenset({
    "README.md",
    "docs/architecture/ROADMAP.md",
    "docs/WORKFLOW.md",
    "docs/architecture/ARCHITECTURE.md",
    "docs/architecture/PROJECT_STATE.md",
})
REQUIRED_CONTINUATION_HEADINGS = (
    "## Context",
    "## Verified state",
    "## Next actions",
    "## Boundaries",
)
SHA_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$")


def is_project_document(path: str) -> bool:
    """Documentation aside from the two mandatory workflow artifacts."""
    if path in CORE_DOCUMENTS:
        return True
    return (
        path.startswith("docs/")
        and path.endswith(".md")
        and path not in {CONTINUATION, CHANGELOG}
    )


def validate_pr_files(
    changed: set[str], continuation_text: str,
    changelog_text: str = "", pr_number: int | None = None,
) -> list[str]:
    errors: list[str] = []
    for path in (CONTINUATION, CHANGELOG):
        if path not in changed:
            errors.append(f"PR must add or update {path}")
    if not any(is_project_document(path) for path in changed):
        errors.append(
            "PR must also update meaningful repository documentation "
            "(README.md, docs/architecture/ROADMAP.md, docs/WORKFLOW.md, or another docs/*.md); "
            "the continuation prompt and changelog alone do not count"
        )
    if len(continuation_text.strip()) < 500:
        errors.append(f"{CONTINUATION} needs a substantive standalone handoff")
    for heading in REQUIRED_CONTINUATION_HEADINGS:
        if heading not in continuation_text:
            errors.append(f"{CONTINUATION} missing required heading: {heading}")
    if "https://github.com/Numillyash/planets-intel" not in continuation_text:
        errors.append(f"{CONTINUATION} must identify the canonical repository")
    if "docs/architecture/ROADMAP.md" not in continuation_text:
        errors.append(f"{CONTINUATION} must tell the successor to read the roadmap")
    if pr_number is not None:
        if type(pr_number) is not int or pr_number <= 0:
            errors.append("PR number must be a positive integer")
        else:
            marker = f"#{pr_number}"
            if marker not in continuation_text:
                errors.append(
                    f"{CONTINUATION} must identify the CURRENT PR {marker}"
                )
            if marker not in changelog_text:
                errors.append(
                    f"{CHANGELOG} must contain the CURRENT PR {marker}"
                )
    return errors


def changed_pr_files(base_sha: str, head_sha: str) -> set[str]:
    """Compare exact trees after workflow fetches both commits.

    -z avoids newline/path parsing issues; added, renamed, modified and
    copied tracked files count. Deleted docs do not satisfy the gate.
    """
    for sha in (base_sha, head_sha):
        if not SHA_PATTERN.fullmatch(sha):
            raise ValueError("base/head must be complete 40-digit commit SHA")
    result = subprocess.run(
        [
            "git", "diff", "--name-only", "-z", "--diff-filter=ACMRT",
            base_sha, head_sha, "--",
        ],
        check=True,
        capture_output=True,
    )
    return {
        path.decode("utf-8", errors="strict")
        for path in result.stdout.split(b"\x00")
        if path
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="PR base commit SHA")
    parser.add_argument("--head", required=True, help="PR head commit SHA")
    parser.add_argument(
        "--pr-number", type=int, required=True,
        help="Current PR number; must occur in both changed handoff files",
    )
    args = parser.parse_args(argv)
    try:
        changed = changed_pr_files(args.base, args.head)
        path = Path(CONTINUATION)
        continuation = path.read_text(encoding="utf-8") if path.is_file() else ""
        changelog_path = Path(CHANGELOG)
        changelog = (
            changelog_path.read_text(encoding="utf-8")
            if changelog_path.is_file() else ""
        )
        failures = validate_pr_files(
            changed, continuation, changelog, args.pr_number,
        )
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"PR handoff gate could not run: {exc}", file=sys.stderr)
        return 2
    if failures:
        print("PR continuity/documentation gate FAILED:", file=sys.stderr)
        for error in failures:
            print(f"  - {error}", file=sys.stderr)
        print(
            "See docs/WORKFLOW.md. Update the handoff, PR changelog, and "
            "project documentation in THIS PR before merging.",
            file=sys.stderr,
        )
        return 1
    print(
        "PR handoff OK: updated continuation prompt, PR changelog "
        "and meaningful project documentation."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
