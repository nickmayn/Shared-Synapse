"""Tests for skills, rules, and knowledge update features."""
import json
from pathlib import Path
import pytest
import yaml
from unittest.mock import AsyncMock, patch


class TestSkillsStore:
    def test_skills_store_module_importable(self):
        from src.db.skills_store import (
            upsert_skill, get_skill, list_skills,
            mark_skills_for_refresh, get_skills_needing_refresh, clear_refresh_flag,
        )
        assert callable(upsert_skill)
        assert callable(get_skill)
        assert callable(list_skills)
        assert callable(mark_skills_for_refresh)


class TestRulesStore:
    def test_rules_store_module_importable(self):
        from src.db.rules_store import upsert_rule, get_rule, list_rules
        assert callable(upsert_rule)
        assert callable(get_rule)
        assert callable(list_rules)


class TestParserSkillsRules:
    def test_parse_skill_type_from_path(self, tmp_path):
        from src.ingestion.parser import parse_file
        skills_dir = tmp_path / "knowledge" / "skills"
        skills_dir.mkdir(parents=True)
        md = skills_dir / "my-skill.md"
        md.write_text(
            "---\nid: my-skill\nname: My Skill\ndescription: A test skill\n"
            "triggers:\n  - test trigger\ndependencies:\n  - auth-system\n---\n"
            "# My Skill\nDo this first.\nDo this second."
        )
        result = parse_file(str(md))
        assert result is not None
        assert result["type"] == "skill"
        assert result["id"] == "my-skill"
        assert result["metadata"]["triggers"] == ["test trigger"]
        assert result["metadata"]["dependencies"] == ["auth-system"]

    def test_parse_rule_type_from_path(self, tmp_path):
        from src.ingestion.parser import parse_file
        rules_dir = tmp_path / "knowledge" / "rules"
        rules_dir.mkdir(parents=True)
        md = rules_dir / "my-rule.md"
        md.write_text(
            "---\nid: my-rule\nname: My Rule\ndescription: A test rule\n"
            "priority: 50\napplies_to:\n  - backend\n---\n# My Rule\nAlways do X."
        )
        result = parse_file(str(md))
        assert result is not None
        assert result["type"] == "rule"
        assert result["metadata"]["priority"] == 50
        assert result["metadata"]["applies_to"] == ["backend"]


class TestBundledRulesAndSkills:
    def test_bundled_rule_and_skill_docs_parse(self):
        from src.ingestion.parser import parse_file

        root = Path(__file__).resolve().parents[1]
        expected_rule_ids = {
            "rule-api-patterns",
            "rule-backend-core",
            "rule-code-quality",
            "rule-deployment-operations",
            "rule-development-workflow",
            "rule-fastapi-architecture",
            "rule-frontend-environment",
            "rule-frontend-styling",
            "rule-python-standards",
            "rule-security",
            "rule-vue3-architecture",
        }
        expected_skill_ids = {
            "add-api-endpoint",
            "agent-customization",
            "debug-auth-flow",
            "find-skills",
            "get-search-view-results",
            "ui-ux-pro-max",
        }
        expected_concept_ids = {
            "auth-system",
            "hybrid-retrieval",
            "shared-synapse-overview",
        }
        expected_design_ids = {"designs-overview"}
        expected_decision_ids = {"use-chromadb"}

        parsed_rule_ids = set()
        for path in sorted((root / "knowledge" / "rules").glob("*.md")):
            parsed = parse_file(str(path))
            assert parsed is not None
            assert parsed["type"] == "rule"
            parsed_rule_ids.add(parsed["id"])

        parsed_skill_ids = set()
        for path in sorted((root / "knowledge" / "skills").glob("*.md")):
            parsed = parse_file(str(path))
            assert parsed is not None
            assert parsed["type"] == "skill"
            parsed_skill_ids.add(parsed["id"])

        parsed_concept_ids = set()
        for path in sorted((root / "knowledge" / "concepts").glob("*.md")):
            parsed = parse_file(str(path))
            assert parsed is not None
            assert parsed["type"] == "concept"
            parsed_concept_ids.add(parsed["id"])

        parsed_design_ids = set()
        for path in sorted((root / "knowledge" / "designs").glob("*.md")):
            parsed = parse_file(str(path))
            assert parsed is not None
            assert parsed["type"] == "design"
            parsed_design_ids.add(parsed["id"])

        parsed_decision_ids = set()
        for path in sorted((root / "knowledge" / "decisions").glob("*.md")):
            parsed = parse_file(str(path))
            assert parsed is not None
            assert parsed["type"] == "decision"
            parsed_decision_ids.add(parsed["id"])

        assert expected_rule_ids.issubset(parsed_rule_ids)
        assert expected_skill_ids.issubset(parsed_skill_ids)
        assert expected_concept_ids.issubset(parsed_concept_ids)
        assert expected_design_ids.issubset(parsed_design_ids)
        assert expected_decision_ids.issubset(parsed_decision_ids)

    def test_context_packs_only_include_known_rules_and_skills(self):
        root = Path(__file__).resolve().parents[1]

        rule_ids = {
            "rule-api-patterns",
            "rule-backend-core",
            "rule-code-quality",
            "rule-deployment-operations",
            "rule-development-workflow",
            "rule-fastapi-architecture",
            "rule-frontend-environment",
            "rule-frontend-styling",
            "rule-python-standards",
            "rule-security",
            "rule-vue3-architecture",
        }
        skill_ids = {
            "add-api-endpoint",
            "agent-customization",
            "debug-auth-flow",
            "find-skills",
            "get-search-view-results",
            "ui-ux-pro-max",
        }
        concept_and_decision_ids = {
            "auth-system",
            "shared-synapse-overview",
            "hybrid-retrieval",
            "use-chromadb",
            "core-brainstem",
        }

        backend_pack = yaml.safe_load((root / "synapses" / "backend.yaml").read_text())
        frontend_pack = yaml.safe_load((root / "synapses" / "frontend.yaml").read_text())

        valid_ids = rule_ids | skill_ids | concept_and_decision_ids

        assert set(backend_pack["includes"]).issubset(valid_ids)
        assert set(frontend_pack["includes"]).issubset(valid_ids)


class TestMCPGetSkill:
    @pytest.mark.asyncio
    async def test_get_skill_not_found(self):
        from src.mcp_server.server import get_skill
        with patch("src.mcp_server.server.audit_log", new_callable=AsyncMock):
            with patch("src.mcp_server.server.db_get_skill", new_callable=AsyncMock, return_value=None):
                result = await get_skill("nonexistent")
        data = json.loads(result)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_get_skill_returns_skill(self):
        from src.mcp_server.server import get_skill
        mock_skill = {
            "id": "debug-auth-flow",
            "name": "Debug Auth Flow",
            "description": "Debug JWT auth",
            "instructions": "Step 1...",
            "triggers": ["auth failure"],
            "dependencies": ["auth-system"],
            "metadata": {},
            "needs_refresh": False,
            "version": 1,
        }
        with patch("src.mcp_server.server.audit_log", new_callable=AsyncMock):
            with patch("src.mcp_server.server.db_get_skill", new_callable=AsyncMock, return_value=mock_skill):
                result = await get_skill("debug-auth-flow")
        data = json.loads(result)
        assert data["id"] == "debug-auth-flow"
        assert data["triggers"] == ["auth failure"]

    @pytest.mark.asyncio
    async def test_get_skill_invalid_id(self):
        from src.mcp_server.server import get_skill
        with pytest.raises(ValueError):
            await get_skill("")


class TestMCPListSkills:
    @pytest.mark.asyncio
    async def test_list_skills_no_context(self):
        from src.mcp_server.server import list_skills
        mock_skills = [{"id": "s1", "name": "Skill 1", "needs_refresh": False}]
        with patch("src.mcp_server.server.audit_log", new_callable=AsyncMock):
            with patch("src.mcp_server.server.db_list_skills", new_callable=AsyncMock, return_value=mock_skills):
                result = await list_skills()
        data = json.loads(result)
        assert data["total"] == 1
        assert data["skills"][0]["id"] == "s1"

    @pytest.mark.asyncio
    async def test_list_skills_with_context(self):
        from src.mcp_server.server import list_skills
        with patch("src.mcp_server.server.audit_log", new_callable=AsyncMock):
            with patch("src.mcp_server.server.db_list_skills", new_callable=AsyncMock, return_value=[]) as mock:
                await list_skills(context="auth")
        mock.assert_called_once_with(filters={"tags": ["auth"]})


class TestMCPUpsertSkill:
    @pytest.mark.asyncio
    async def test_upsert_skill_invalid_triggers_json(self):
        from src.mcp_server.server import upsert_skill
        with pytest.raises(ValueError, match="triggers"):
            await upsert_skill("id", "name", "desc", "instructions", triggers="not-json")

    @pytest.mark.asyncio
    async def test_upsert_skill_success(self):
        from src.mcp_server.server import upsert_skill
        with patch("src.mcp_server.server.audit_log", new_callable=AsyncMock):
            with patch("src.mcp_server.server.db_upsert_skill", new_callable=AsyncMock):
                with patch("src.mcp_server.server.upsert_document", new_callable=AsyncMock):
                    with patch("src.mcp_server.server.delete_chunks_for_document", new_callable=AsyncMock):
                        with patch("src.mcp_server.server.upsert_chunk", new_callable=AsyncMock):
                            result = await upsert_skill(
                                "test-skill", "Test Skill", "Does testing",
                                "Step 1: do X\nStep 2: do Y",
                                triggers='["test trigger"]',
                                dependencies='["auth-system"]',
                            )
        data = json.loads(result)
        assert data["status"] == "upserted"
        assert data["id"] == "test-skill"


class TestMCPGetRule:
    @pytest.mark.asyncio
    async def test_get_rule_not_found(self):
        from src.mcp_server.server import get_rule
        with patch("src.mcp_server.server.audit_log", new_callable=AsyncMock):
            with patch("src.mcp_server.server.db_get_rule", new_callable=AsyncMock, return_value=None):
                result = await get_rule("nonexistent")
        data = json.loads(result)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_get_rule_returns_rule(self):
        from src.mcp_server.server import get_rule
        mock_rule = {
            "id": "rule-security",
            "name": "Security Rules",
            "description": "Mandatory security",
            "content": "# Security\n...",
            "priority": 100,
            "applies_to": ["backend"],
            "metadata": {},
        }
        with patch("src.mcp_server.server.audit_log", new_callable=AsyncMock):
            with patch("src.mcp_server.server.db_get_rule", new_callable=AsyncMock, return_value=mock_rule):
                result = await get_rule("rule-security")
        data = json.loads(result)
        assert data["id"] == "rule-security"
        assert data["priority"] == 100


class TestMCPListRules:
    @pytest.mark.asyncio
    async def test_list_rules_returns_json(self):
        from src.mcp_server.server import list_rules
        mock_rules = [
            {"id": "rule-security", "priority": 100},
            {"id": "rule-code-quality", "priority": 10},
        ]
        with patch("src.mcp_server.server.audit_log", new_callable=AsyncMock):
            with patch("src.mcp_server.server.db_list_rules", new_callable=AsyncMock, return_value=mock_rules):
                result = await list_rules()
        data = json.loads(result)
        assert data["total"] == 2

    @pytest.mark.asyncio
    async def test_list_rules_passes_context(self):
        from src.mcp_server.server import list_rules
        with patch("src.mcp_server.server.audit_log", new_callable=AsyncMock):
            with patch("src.mcp_server.server.db_list_rules", new_callable=AsyncMock, return_value=[]) as mock:
                await list_rules(context="backend")
        mock.assert_called_once_with(context="backend")


class TestMCPUpdateKnowledge:
    @pytest.mark.asyncio
    async def test_update_knowledge_not_found(self):
        from src.mcp_server.server import update_knowledge
        with patch("src.mcp_server.server.audit_log", new_callable=AsyncMock):
            with patch("src.mcp_server.server.db_get_document", new_callable=AsyncMock, return_value=None):
                result = await update_knowledge("nonexistent", "some content")
        data = json.loads(result)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_update_knowledge_invalid_metadata(self):
        from src.mcp_server.server import update_knowledge
        with pytest.raises(ValueError, match="JSON"):
            await update_knowledge("id", "content", metadata="not-json")


class TestMCPDeleteKnowledge:
    @pytest.mark.asyncio
    async def test_delete_knowledge_success(self):
        from src.mcp_server.server import delete_knowledge
        with patch("src.mcp_server.server.audit_log", new_callable=AsyncMock):
            with patch("src.mcp_server.server.pipeline_delete_knowledge",
                       new_callable=AsyncMock, return_value=True):
                result = await delete_knowledge("doc-to-delete")
        data = json.loads(result)
        assert data["status"] == "deleted"

    @pytest.mark.asyncio
    async def test_delete_knowledge_failure(self):
        from src.mcp_server.server import delete_knowledge
        with patch("src.mcp_server.server.audit_log", new_callable=AsyncMock):
            with patch("src.mcp_server.server.pipeline_delete_knowledge",
                       new_callable=AsyncMock, return_value=False):
                result = await delete_knowledge("bad-doc")
        data = json.loads(result)
        assert "error" in data


class TestMCPReindexKnowledge:
    @pytest.mark.asyncio
    async def test_reindex_knowledge_returns_stats(self):
        from src.mcp_server.server import reindex_knowledge
        mock_stats = {"total": 10, "success": 9, "failed": 1}
        with patch("src.mcp_server.server.audit_log", new_callable=AsyncMock):
            with patch("src.mcp_server.server.run_ingestion",
                       new_callable=AsyncMock, return_value=mock_stats):
                result = await reindex_knowledge()
        data = json.loads(result)
        assert data["status"] == "complete"
        assert data["total"] == 10
        assert data["success"] == 9
