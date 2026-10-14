import ast
from pathlib import Path
import unittest


VERSIONS_DIR = Path(__file__).resolve().parents[1] / "alembic" / "versions"
MAX_ALEMBIC_VERSION_LENGTH = 32


def _revision_id(path: Path) -> str | None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or target.id != "revision":
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return node.value.value
    return None


class AlembicRevisionIdTests(unittest.TestCase):
    def test_revision_ids_fit_default_alembic_version_column(self) -> None:
        failures: list[str] = []
        for path in sorted(VERSIONS_DIR.glob("*.py")):
            if path.name.startswith("__"):
                continue
            revision = _revision_id(path)
            if revision is None:
                failures.append(f"{path.name}: missing literal revision id")
                continue
            if len(revision) > MAX_ALEMBIC_VERSION_LENGTH:
                failures.append(
                    f"{path.name}: revision {revision!r} is {len(revision)} chars "
                    f"(max {MAX_ALEMBIC_VERSION_LENGTH})"
                )

        self.assertEqual(failures, [], "\n".join(failures))


if __name__ == "__main__":
    unittest.main()
