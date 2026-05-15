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


class TestInferCandidateTypeSkillFormat:
    """Ensure infer_candidate_type only returns skill for properly formatted paths."""

    def test_skill_md_suffix_is_a_skill(self):
        from src.github_import import infer_candidate_type
        assert infer_candidate_type("knowledge/skills/debug-auth.skill.md") == "skill"

    def test_file_in_skills_dir_is_a_skill(self):
        from src.github_import import infer_candidate_type
        assert infer_candidate_type("knowledge/skills/add-endpoint.md") == "skill"

    def test_readme_in_skills_dir_is_not_a_skill(self):
        from src.github_import import infer_candidate_type
        assert infer_candidate_type("knowledge/skills/README.md") is None

    def test_readme_case_insensitive_in_skills_dir(self):
        from src.github_import import infer_candidate_type
        assert infer_candidate_type("knowledge/skills/Readme.md") is None

    def test_changelog_in_skills_dir_is_not_a_skill(self):
        from src.github_import import infer_candidate_type
        assert infer_candidate_type("knowledge/skills/CHANGELOG.md") is None

    def test_index_in_skills_dir_is_not_a_skill(self):
        from src.github_import import infer_candidate_type
        assert infer_candidate_type("skills/index.md") is None

    def test_readme_in_rules_dir_is_not_a_rule(self):
        from src.github_import import infer_candidate_type
        assert infer_candidate_type("knowledge/rules/README.md") is None

    def test_rule_file_in_rules_dir_is_a_rule(self):
        from src.github_import import infer_candidate_type
        assert infer_candidate_type("knowledge/rules/backend-core.md") == "rule"

    def test_generic_docs_outside_skill_dirs_are_unclassified(self):
        """Generic filenames outside skill/rule dirs should still return None."""
        from src.github_import import infer_candidate_type
        assert infer_candidate_type("README.md") is None
        assert infer_candidate_type("docs/overview.md") is None

    def test_select_import_candidates_excludes_generic_skill_docs(self):
        """select_import_candidates should not include README or CHANGELOG as skills."""
        from src.github_import import select_import_candidates

        tree = [
            {"path": "knowledge/skills/README.md", "type": "blob"},
            {"path": "knowledge/skills/CHANGELOG.md", "type": "blob"},
            {"path": "knowledge/skills/add-endpoint.md", "type": "blob"},
            {"path": "knowledge/skills/debug-auth-flow.md", "type": "blob"},
        ]

        candidates = select_import_candidates(tree, "octo/shared-brain", "main", kind="skill")
        paths = [c["path"] for c in candidates]
        assert "knowledge/skills/README.md" not in paths
        assert "knowledge/skills/CHANGELOG.md" not in paths
        assert "knowledge/skills/add-endpoint.md" in paths
        assert "knowledge/skills/debug-auth-flow.md" in paths