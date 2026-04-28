"""Tests for nominations and conversations features."""
import json
import pytest
from unittest.mock import AsyncMock, patch


class TestNominationsStore:
    def test_nominations_store_importable(self):
        from src.db.nominations_store import (
            nominate_knowledge,
            get_nomination,
            list_nominations,
            vote_nomination,
            update_nomination_status,
            NOMINATION_STATUSES,
        )
        assert callable(nominate_knowledge)
        assert callable(get_nomination)
        assert callable(list_nominations)
        assert callable(vote_nomination)
        assert callable(update_nomination_status)
        assert "pending" in NOMINATION_STATUSES
        assert "approved" in NOMINATION_STATUSES
        assert "rejected" in NOMINATION_STATUSES


class TestConversationsStore:
    def test_conversations_store_importable(self):
        from src.db.conversations_store import (
            add_conversation_entry,
            get_conversation_tree,
            list_conversations,
        )
        assert callable(add_conversation_entry)
        assert callable(get_conversation_tree)
        assert callable(list_conversations)


class TestNominateMCPTool:
    @pytest.mark.asyncio
    async def test_nominate_validates_empty_id(self):
        from src.mcp_server.server import nominate_knowledge
        with pytest.raises(ValueError, match="id"):
            await nominate_knowledge("", "user1", "concept", "Some content")

    @pytest.mark.asyncio
    async def test_nominate_validates_empty_nominator(self):
        from src.mcp_server.server import nominate_knowledge
        with pytest.raises(ValueError, match="nominator"):
            await nominate_knowledge("nom-1", "", "concept", "Some content")

    @pytest.mark.asyncio
    async def test_nominate_validates_invalid_type(self):
        from src.mcp_server.server import nominate_knowledge
        with patch("src.mcp_server.server.audit_log", new_callable=AsyncMock):
            with pytest.raises(ValueError, match="type"):
                await nominate_knowledge("nom-1", "user1", "invalid_type", "Some content")

    @pytest.mark.asyncio
    async def test_nominate_validates_bad_metadata_json(self):
        from src.mcp_server.server import nominate_knowledge
        with patch("src.mcp_server.server.audit_log", new_callable=AsyncMock):
            with pytest.raises(ValueError, match="JSON"):
                await nominate_knowledge("nom-1", "user1", "concept", "Some content",
                                         metadata="not-json")

    @pytest.mark.asyncio
    async def test_nominate_success(self):
        from src.mcp_server.server import nominate_knowledge
        with patch("src.mcp_server.server.audit_log", new_callable=AsyncMock):
            with patch("src.mcp_server.server.db_nominate_knowledge", new_callable=AsyncMock):
                result = await nominate_knowledge("nom-1", "alice", "concept", "Great idea here")
        data = json.loads(result)
        assert data["status"] == "nominated"
        assert data["id"] == "nom-1"
        assert data["nominator"] == "alice"
        assert data["type"] == "concept"


class TestListNominationsMCPTool:
    @pytest.mark.asyncio
    async def test_list_nominations_invalid_status(self):
        from src.mcp_server.server import list_nominations
        with pytest.raises(ValueError, match="status"):
            await list_nominations(status="invalid")

    @pytest.mark.asyncio
    async def test_list_nominations_returns_json(self):
        from src.mcp_server.server import list_nominations
        mock_noms = [
            {"id": "n1", "nominator": "alice", "type": "concept", "content": "...",
             "status": "pending", "upvotes": 2, "downvotes": 0, "voters": [],
             "metadata": {}, "created_at": "2026-01-01T00:00:00", "updated_at": "2026-01-01T00:00:00"},
        ]
        with patch("src.mcp_server.server.audit_log", new_callable=AsyncMock):
            with patch("src.mcp_server.server.db_list_nominations",
                       new_callable=AsyncMock, return_value=mock_noms):
                result = await list_nominations(status="pending")
        data = json.loads(result)
        assert data["total"] == 1
        assert data["nominations"][0]["id"] == "n1"


class TestVoteNominationMCPTool:
    @pytest.mark.asyncio
    async def test_vote_validates_empty_nomination_id(self):
        from src.mcp_server.server import vote_nomination
        with pytest.raises(ValueError, match="nomination_id"):
            await vote_nomination("", "bob", "up")

    @pytest.mark.asyncio
    async def test_vote_validates_invalid_vote(self):
        from src.mcp_server.server import vote_nomination
        with pytest.raises(ValueError, match="'up' or 'down'"):
            await vote_nomination("nom-1", "bob", "sideways")

    @pytest.mark.asyncio
    async def test_vote_not_found(self):
        from src.mcp_server.server import vote_nomination
        with patch("src.mcp_server.server.audit_log", new_callable=AsyncMock):
            with patch("src.mcp_server.server.db_vote_nomination",
                       new_callable=AsyncMock, return_value=None):
                result = await vote_nomination("nom-999", "bob", "up")
        data = json.loads(result)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_vote_success(self):
        from src.mcp_server.server import vote_nomination
        updated = {"id": "nom-1", "nominator": "alice", "type": "concept", "content": "...",
                   "status": "pending", "upvotes": 1, "downvotes": 0, "voters": [],
                   "metadata": {}, "created_at": "2026-01-01T00:00:00",
                   "updated_at": "2026-01-01T00:00:01"}
        with patch("src.mcp_server.server.audit_log", new_callable=AsyncMock):
            with patch("src.mcp_server.server.db_vote_nomination",
                       new_callable=AsyncMock, return_value=updated):
                result = await vote_nomination("nom-1", "bob", "up")
        data = json.loads(result)
        assert data["status"] == "voted"
        assert data["upvotes"] == 1


class TestApproveNominationMCPTool:
    @pytest.mark.asyncio
    async def test_approve_not_found(self):
        from src.mcp_server.server import approve_nomination
        with patch("src.mcp_server.server.audit_log", new_callable=AsyncMock):
            with patch("src.mcp_server.server.db_get_nomination",
                       new_callable=AsyncMock, return_value=None):
                result = await approve_nomination("nom-999")
        data = json.loads(result)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_approve_already_approved(self):
        from src.mcp_server.server import approve_nomination
        existing = {"id": "nom-1", "nominator": "alice", "type": "concept",
                    "content": "Great content", "status": "approved",
                    "upvotes": 1, "downvotes": 0, "voters": [], "metadata": {},
                    "created_at": "2026-01-01T00:00:00", "updated_at": "2026-01-01T00:00:00"}
        with patch("src.mcp_server.server.audit_log", new_callable=AsyncMock):
            with patch("src.mcp_server.server.db_get_nomination",
                       new_callable=AsyncMock, return_value=existing):
                result = await approve_nomination("nom-1")
        data = json.loads(result)
        assert data["status"] == "already_approved"

    @pytest.mark.asyncio
    async def test_approve_success(self):
        from src.mcp_server.server import approve_nomination
        nomination = {"id": "nom-1", "nominator": "alice", "type": "concept",
                      "content": "Great content to index", "status": "pending",
                      "upvotes": 3, "downvotes": 0, "voters": [], "metadata": {},
                      "created_at": "2026-01-01T00:00:00", "updated_at": "2026-01-01T00:00:00"}
        fake_chunks = [{"id": "c1", "content": "Great content to index",
                        "metadata": {"document_type": "concept"}}]
        fake_embeddings = [[0.0] * 384]
        with patch("src.mcp_server.server.audit_log", new_callable=AsyncMock):
            with patch("src.mcp_server.server.db_get_nomination",
                       new_callable=AsyncMock, return_value=nomination):
                with patch("src.mcp_server.server.db_update_nomination_status",
                           new_callable=AsyncMock):
                    with patch("src.mcp_server.server.upsert_document",
                               new_callable=AsyncMock):
                        with patch("src.mcp_server.server.chunk_text",
                                   return_value=fake_chunks):
                            with patch("src.mcp_server.server.embed_texts_batch",
                                       return_value=fake_embeddings):
                                with patch("src.mcp_server.server.delete_chunks_for_document",
                                           new_callable=AsyncMock):
                                    with patch("src.mcp_server.server.upsert_chunk",
                                               new_callable=AsyncMock):
                                        result = await approve_nomination("nom-1")
        data = json.loads(result)
        assert data["status"] == "approved"
        assert data["id"] == "nom-1"
        assert data["chunks"] == 1


class TestRejectNominationMCPTool:
    @pytest.mark.asyncio
    async def test_reject_not_found(self):
        from src.mcp_server.server import reject_nomination
        with patch("src.mcp_server.server.audit_log", new_callable=AsyncMock):
            with patch("src.mcp_server.server.db_get_nomination",
                       new_callable=AsyncMock, return_value=None):
                result = await reject_nomination("nom-999")
        data = json.loads(result)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_reject_success(self):
        from src.mcp_server.server import reject_nomination
        nomination = {"id": "nom-1", "nominator": "alice", "type": "concept",
                      "content": "...", "status": "pending",
                      "upvotes": 0, "downvotes": 1, "voters": [], "metadata": {},
                      "created_at": "2026-01-01T00:00:00", "updated_at": "2026-01-01T00:00:00"}
        with patch("src.mcp_server.server.audit_log", new_callable=AsyncMock):
            with patch("src.mcp_server.server.db_get_nomination",
                       new_callable=AsyncMock, return_value=nomination):
                with patch("src.mcp_server.server.db_update_nomination_status",
                           new_callable=AsyncMock):
                    result = await reject_nomination("nom-1")
        data = json.loads(result)
        assert data["status"] == "rejected"


class TestAddConversationEntryMCPTool:
    @pytest.mark.asyncio
    async def test_add_validates_empty_user_id(self):
        from src.mcp_server.server import add_conversation_entry
        with pytest.raises(ValueError, match="user_id"):
            await add_conversation_entry("", "user", "Hello")

    @pytest.mark.asyncio
    async def test_add_validates_invalid_role(self):
        from src.mcp_server.server import add_conversation_entry
        with pytest.raises(ValueError, match="role"):
            await add_conversation_entry("alice", "bot", "Hello")

    @pytest.mark.asyncio
    async def test_add_success_with_context(self):
        from src.mcp_server.server import add_conversation_entry
        with patch("src.mcp_server.server.audit_log", new_callable=AsyncMock):
            with patch("src.mcp_server.server.db_add_conversation_entry",
                       new_callable=AsyncMock, return_value="entry-abc"):
                result = await add_conversation_entry(
                    "alice", "user", "Hello there",
                    conversation_id="project-alpha", session_id="sess-1",
                )
        data = json.loads(result)
        assert data["status"] == "added"
        assert data["entry_id"] == "entry-abc"
        assert data["user_id"] == "alice"
        assert data["conversation_id"] == "project-alpha"
        assert data["session_id"] == "sess-1"

    @pytest.mark.asyncio
    async def test_add_success_without_context(self):
        """conversation_id and session_id default to None and are auto-assigned by the store."""
        from src.mcp_server.server import add_conversation_entry
        with patch("src.mcp_server.server.audit_log", new_callable=AsyncMock):
            with patch("src.mcp_server.server.db_add_conversation_entry",
                       new_callable=AsyncMock, return_value="entry-xyz"):
                result = await add_conversation_entry("alice", "agent", "I can help!")
        data = json.loads(result)
        assert data["status"] == "added"
        assert data["entry_id"] == "entry-xyz"


class TestGetConversationMCPTool:
    @pytest.mark.asyncio
    async def test_get_validates_empty_user_id(self):
        from src.mcp_server.server import get_conversation
        with pytest.raises(ValueError, match="user_id"):
            await get_conversation("")

    @pytest.mark.asyncio
    async def test_get_returns_nested_tree(self):
        from src.mcp_server.server import get_conversation
        mock_tree = {
            "project-alpha": {
                "conversation_id": "project-alpha",
                "user_id": "alice",
                "sessions": {
                    "sess-1": {
                        "session_id": "sess-1",
                        "entry_count": 2,
                        "started_at": "2026-01-01T00:00:00",
                        "latest_at": "2026-01-01T00:00:01",
                        "entries": [
                            {"id": "e1", "user_id": "alice", "role": "user",
                             "content": "Hello", "created_at": "2026-01-01T00:00:00"},
                            {"id": "e2", "user_id": "alice", "role": "agent",
                             "content": "Hi there", "created_at": "2026-01-01T00:00:01"},
                        ],
                    }
                },
            }
        }
        with patch("src.mcp_server.server.audit_log", new_callable=AsyncMock):
            with patch("src.mcp_server.server.db_get_conversation_tree",
                       new_callable=AsyncMock, return_value=mock_tree):
                result = await get_conversation("alice", conversation_id="project-alpha")
        data = json.loads(result)
        assert data["user_id"] == "alice"
        assert data["conversation_count"] == 1
        conv = data["conversations"]["project-alpha"]
        assert conv["sessions"]["sess-1"]["entry_count"] == 2
        assert conv["sessions"]["sess-1"]["entries"][0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_get_respects_limit_cap(self):
        from src.mcp_server.server import get_conversation
        with patch("src.mcp_server.server.audit_log", new_callable=AsyncMock):
            with patch("src.mcp_server.server.db_get_conversation_tree",
                       new_callable=AsyncMock, return_value={}) as mock_fn:
                await get_conversation("alice", limit=1000)
                _, kwargs = mock_fn.call_args
                assert kwargs["limit"] == 500


class TestListConversationsMCPTool:
    @pytest.mark.asyncio
    async def test_list_validates_empty_user_id(self):
        from src.mcp_server.server import list_conversations
        with pytest.raises(ValueError, match="user_id"):
            await list_conversations("")

    @pytest.mark.asyncio
    async def test_list_returns_conversation_summaries(self):
        from src.mcp_server.server import list_conversations
        mock_conversations = [
            {"conversation_id": "project-alpha", "user_id": "alice",
             "session_count": 3, "total_entries": 12,
             "latest_at": "2026-01-02T00:00:00"},
            {"conversation_id": "project-beta", "user_id": "alice",
             "session_count": 1, "total_entries": 2,
             "latest_at": "2026-01-01T00:00:00"},
        ]
        with patch("src.mcp_server.server.audit_log", new_callable=AsyncMock):
            with patch("src.mcp_server.server.db_list_conversations",
                       new_callable=AsyncMock, return_value=mock_conversations):
                result = await list_conversations("alice")
        data = json.loads(result)
        assert data["total"] == 2
        assert data["conversations"][0]["conversation_id"] == "project-alpha"
        assert data["conversations"][0]["session_count"] == 3
