"""Focused regression tests for synapse loading and GitHub import helpers."""
from pathlib import Path


def test_synapses_dir_points_to_repo_synapses(monkeypatch):
    """Default synapse resolution should target the repo's synapses directory."""
    from src.db.synapses_store import _synapses_dir

    monkeypatch.delenv("SYNAPSES_DIR", raising=False)
    expected = Path(__file__).resolve().parents[2] / "synapses"
    assert _synapses_dir() == expected


def test_select_import_candidates_prefers_knowledge_paths():
    """GitHub candidate selection should prioritize likely knowledge files."""
    from src.github_import import select_import_candidates

    tree = [
        {"path": "docs/security-rule.md", "type": "blob"},
        {"path": "knowledge/rules/backend-core.md", "type": "blob"},
        {"path": "knowledge/skills/debug-auth-flow.md", "type": "blob"},
        {"path": "tools/api-gateway-config.json", "type": "blob"},
    ]

    candidates = select_import_candidates(tree, "octo/shared-brain", "main", kind="rule")
    assert candidates[0]["path"] == "knowledge/rules/backend-core.md"
    assert candidates[0]["type"] == "rule"


def test_parse_import_document_uses_frontmatter_metadata():
    """Remote markdown imports should preserve frontmatter IDs and descriptions."""
    from src.github_import import parse_import_document

    content = (
        "---\n"
        "id: rule-security\n"
        "name: Security Baseline\n"
        "description: Keep secrets out of code\n"
        "---\n"
        "# Security\n"
        "Never hardcode credentials.\n"
    )

    document = parse_import_document(
        repo_full_name="octo/shared-brain",
        default_branch="main",
        path="knowledge/rules/security.md",
        content=content,
        inferred_type="rule",
    )

    assert document["id"] == "rule-security"
    assert document["type"] == "rule"
    assert document["description"] == "Keep secrets out of code"
    assert document["metadata"]["source_repo"] == "octo/shared-brain"