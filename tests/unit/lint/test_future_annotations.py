from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = PROJECT_ROOT / "src" / "good_agent"


def _has_future_annotations(tree: ast.Module) -> bool:
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            if any(alias.name == "annotations" for alias in node.names):
                return True
    return False


class _StringUnionVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.has_string_union = False

    def visit_BinOp(self, node: ast.BinOp) -> None:  # noqa: N802 (ast API)
        if isinstance(node.op, ast.BitOr):
            for side in (node.left, node.right):
                if isinstance(side, ast.Constant) and isinstance(side.value, str):
                    self.has_string_union = True
        self.generic_visit(node)


def _uses_string_union(tree: ast.Module) -> bool:
    visitor = _StringUnionVisitor()
    visitor.visit(tree)
    return visitor.has_string_union


def test_string_union_forward_refs_require_future_annotations() -> None:
    violations: list[Path] = []

    for path in SOURCE_DIR.rglob("*.py"):
        source = path.read_text()
        tree: ast.Module = ast.parse(source)
        if _uses_string_union(tree) and not _has_future_annotations(tree):
            violations.append(path.relative_to(PROJECT_ROOT))

    assert not violations, (
        "The following modules use PEP 604 unions with string literals but lack "
        "'from __future__ import annotations':\n"
        + "\n".join(str(path) for path in violations)
    )
