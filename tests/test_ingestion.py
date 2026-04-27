"""Tests for the ingestion pipeline."""
import json
import textwrap
from pathlib import Path

import pytest

from src.ingestion.chunker import chunk_text, count_tokens
from src.ingestion.parser import _path_to_id, parse_file


class TestParser:
    def test_parse_markdown_with_frontmatter(self, tmp_path):
        md_file = tmp_path / "test.md"
        md_file.write_text(textwrap.dedent("""\
            ---
            id: test-doc
            title: Test Document
            tags: [test, demo]
            ---

            # Test Document

            This is a test document with some content.
            """))
        result = parse_file(str(md_file))
        assert result is not None
        assert result["id"] == "test-doc"
        assert "Test Document" in result["content"]
        assert result["metadata"]["title"] == "Test Document"
        assert result["metadata"]["tags"] == ["test", "demo"]

    def test_parse_markdown_without_frontmatter(self, tmp_path):
        md_file = tmp_path / "test.md"
        md_file.write_text("# Hello\n\nSome content.")
        result = parse_file(str(md_file))
        assert result is not None
        assert result["content"] == "# Hello\n\nSome content."

    def test_parse_yaml_context_pack(self, tmp_path):
        yaml_file = tmp_path / "backend.yaml"
        yaml_file.write_text(textwrap.dedent("""\
            name: backend
            description: Backend context pack
            tags:
              - backend
            """))
        result = parse_file(str(yaml_file))
        assert result is not None
        assert result["id"] == "backend"
        assert result["type"] == "context_pack"

    def test_parse_json_tool(self, tmp_path):
        json_file = tmp_path / "my-tool.json"
        json_file.write_text(json.dumps({
            "id": "my-tool",
            "description": "A test tool",
            "input_schema": {},
            "output_schema": {},
            "metadata": {"tags": ["test"]},
        }))
        result = parse_file(str(json_file))
        assert result is not None
        assert result["id"] == "my-tool"
        assert result["type"] == "tool"

    def test_parse_unsupported_returns_none(self, tmp_path):
        txt_file = tmp_path / "file.txt"
        txt_file.write_text("hello")
        result = parse_file(str(txt_file))
        assert result is None

    def test_document_type_from_path(self, tmp_path):
        systems_dir = tmp_path / "knowledge" / "systems"
        systems_dir.mkdir(parents=True)
        md = systems_dir / "my-system.md"
        md.write_text("---\nid: my-system\n---\n# System\nContent here.")
        result = parse_file(str(md))
        assert result["type"] == "system"


class TestChunker:
    def test_chunk_short_text(self):
        text = "This is a short document."
        chunks = chunk_text(text, "doc-1")
        assert len(chunks) >= 1
        assert chunks[0]["content"] == text

    def test_chunk_preserves_doc_id(self):
        text = "Short text"
        chunks = chunk_text(text, "my-doc")
        assert all("my-doc" in c["id"] for c in chunks)

    def test_chunk_ids_unique(self):
        text = "\n\n".join([f"Section {i}: " + "word " * 100 for i in range(10)])
        chunks = chunk_text(text, "doc-1")
        ids = [c["id"] for c in chunks]
        assert len(ids) == len(set(ids))

    def test_chunk_metadata_has_token_count(self):
        text = "This is some text with enough content to be meaningful."
        chunks = chunk_text(text, "doc-1")
        for chunk in chunks:
            assert "token_count" in chunk["metadata"]
            assert chunk["metadata"]["token_count"] > 0

    def test_count_tokens(self):
        assert count_tokens("hello world") > 0
        assert count_tokens("") == 0

    def test_chunk_large_text_multiple_chunks(self):
        text = "This is a sentence with many words. " * 200
        chunks = chunk_text(text, "large-doc", min_tokens=10, max_tokens=50)
        assert len(chunks) > 1
