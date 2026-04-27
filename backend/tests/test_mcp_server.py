"""Tests for the MCP server endpoints."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestSearchKnowledge:
    @pytest.mark.asyncio
    async def test_search_validates_empty_query(self):
        from src.mcp_server.server import search_knowledge
        with pytest.raises(ValueError, match="empty"):
            await search_knowledge("")

    @pytest.mark.asyncio
    async def test_search_validates_long_query(self):
        from src.mcp_server.server import search_knowledge
        with pytest.raises(ValueError, match="4096"):
            await search_knowledge("x" * 5000)

    @pytest.mark.asyncio
    async def test_search_invalid_filters_json(self):
        from src.mcp_server.server import search_knowledge
        with patch("src.mcp_server.server.audit_log", new_callable=AsyncMock):
            with pytest.raises(ValueError, match="JSON"):
                await search_knowledge("query", filters="not-json")

    @pytest.mark.asyncio
    async def test_search_returns_json(self):
        from src.mcp_server.server import search_knowledge
        mock_results = [
            {
                "chunk_id": "c1",
                "document_id": "d1",
                "chunk_content": "test",
                "similarity": 0.9,
                "document_type": "system",
                "document_metadata": {},
                "chunk_metadata": {},
                "score": 0.9,
            }
        ]
        with patch("src.mcp_server.server.audit_log", new_callable=AsyncMock):
            with patch("src.mcp_server.server.hybrid_search", new_callable=AsyncMock, return_value=mock_results):
                with patch("src.mcp_server.server.rank_results", return_value=mock_results):
                    result = await search_knowledge("test query")
        data = json.loads(result)
        assert "results" in data
        assert data["total"] == 1


class TestGetDocument:
    @pytest.mark.asyncio
    async def test_get_document_not_found(self):
        from src.mcp_server.server import get_document
        with patch("src.mcp_server.server.audit_log", new_callable=AsyncMock):
            with patch("src.mcp_server.server.db_get_document", new_callable=AsyncMock, return_value=None):
                result = await get_document("nonexistent")
        data = json.loads(result)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_get_document_returns_doc(self):
        from src.mcp_server.server import get_document
        mock_doc = {"id": "auth-system", "type": "system", "content": "...", "metadata": {}}
        with patch("src.mcp_server.server.audit_log", new_callable=AsyncMock):
            with patch("src.mcp_server.server.db_get_document", new_callable=AsyncMock, return_value=mock_doc):
                result = await get_document("auth-system")
        data = json.loads(result)
        assert data["id"] == "auth-system"


class TestExecuteTool:
    @pytest.mark.asyncio
    async def test_execute_tool_invalid_id(self):
        from src.mcp_server.server import execute_tool
        with pytest.raises(ValueError):
            await execute_tool("../evil", '{}')

    @pytest.mark.asyncio
    async def test_execute_tool_invalid_input_json(self):
        from src.mcp_server.server import execute_tool
        with pytest.raises(ValueError, match="JSON"):
            await execute_tool("my-tool", "not-json")

    @pytest.mark.asyncio
    async def test_execute_tool_not_found(self):
        from src.mcp_server.server import execute_tool
        with patch("src.mcp_server.server.get_tool", new_callable=AsyncMock, return_value=None):
            with patch("src.mcp_server.server.audit_log", new_callable=AsyncMock):
                result = await execute_tool("nonexistent-tool", '{}')
        data = json.loads(result)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_execute_tool_success(self):
        from src.mcp_server.server import execute_tool
        mock_tool = {
            "id": "my-tool",
            "description": "A tool",
            "input_schema": {"required": ["action"]},
            "output_schema": {},
            "metadata": {},
        }
        with patch("src.mcp_server.server.get_tool", new_callable=AsyncMock, return_value=mock_tool):
            with patch("src.mcp_server.server.audit_log", new_callable=AsyncMock):
                result = await execute_tool("my-tool", '{"action": "test"}')
        data = json.loads(result)
        assert data["status"] == "executed"
        assert data["tool_id"] == "my-tool"


class TestSecurity:
    def test_validate_query_empty(self):
        from src.mcp_server.security import validate_query
        with pytest.raises(ValueError):
            validate_query("")

    def test_validate_query_too_long(self):
        from src.mcp_server.security import validate_query
        with pytest.raises(ValueError):
            validate_query("x" * 5000)

    def test_validate_query_ok(self):
        from src.mcp_server.security import validate_query
        assert validate_query("  hello  ") == "hello"

    def test_validate_tool_id_path_traversal(self):
        from src.mcp_server.security import validate_tool_id
        with pytest.raises(ValueError):
            validate_tool_id("../secret")

    def test_validate_tool_id_ok(self):
        from src.mcp_server.security import validate_tool_id
        assert validate_tool_id("my-tool") == "my-tool"

    def test_validate_tool_input_missing_required(self):
        from src.mcp_server.security import validate_tool_input
        with pytest.raises(ValueError, match="Missing required field"):
            validate_tool_input({}, {"required": ["action"]})

    def test_validate_tool_input_ok(self):
        from src.mcp_server.security import validate_tool_input
        validate_tool_input({"action": "test"}, {"required": ["action"]})
