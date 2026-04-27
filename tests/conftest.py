"""
Shared test fixtures and mocks.
Provides a tiktoken mock so chunker tests run without network access.
"""
import pytest
from unittest.mock import MagicMock, patch


class _FakeEncoder:
    """Simple whitespace tokenizer stand-in for tiktoken in tests."""

    def encode(self, text: str):
        return text.split() if text else []

    def decode(self, tokens) -> str:
        return " ".join(tokens)


@pytest.fixture(autouse=True)
def mock_tiktoken(monkeypatch):
    """Replace tiktoken encoder with a fast offline stub for all tests."""
    fake = _FakeEncoder()

    import src.ingestion.chunker as chunker_mod
    monkeypatch.setattr(chunker_mod, "_encoder", fake)

    # Patch _get_encoder so it returns the fake without triggering download
    monkeypatch.setattr(chunker_mod, "_get_encoder", lambda: fake)
