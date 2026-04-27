"""
Shared test fixtures and mocks.
Provides a tiktoken mock so chunker tests run without network access.
Also mocks sentence_transformers so embedding tests run without the library installed.
"""
import sys
import types
import pytest
from unittest.mock import MagicMock, patch


def _install_sentence_transformers_mock():
    """Install a minimal sentence_transformers stub into sys.modules."""
    if "sentence_transformers" in sys.modules:
        return

    import numpy as np

    class _FakeModel:
        def encode(self, texts, **kwargs):
            if isinstance(texts, str):
                return np.zeros(384, dtype="float32")
            return np.zeros((len(texts), 384), dtype="float32")

    mod = types.ModuleType("sentence_transformers")
    mod.SentenceTransformer = lambda *a, **kw: _FakeModel()
    sys.modules["sentence_transformers"] = mod


_install_sentence_transformers_mock()


class _FakeEncoder:
    """
    Whitespace-based tokenizer stand-in for tiktoken in tests.

    NOTE: Token counts here differ from real tiktoken (word-count vs BPE).
    This is intentional: tests validate chunking *logic* (splitting, IDs,
    metadata structure) not exact token boundaries, so the approximation is
    acceptable and avoids a network download in CI.
    """

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

