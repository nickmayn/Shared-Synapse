import re
from typing import List, Optional

# Minimum token count for a leftover trailing chunk to be kept.
# Lower than min_tokens (300) because this is the final piece of a document
# that has already had full-sized chunks extracted from it.
_MIN_FINAL_CHUNK_TOKENS = 50

_encoder = None


def _get_encoder():
    global _encoder
    if _encoder is None:
        import tiktoken
        _encoder = tiktoken.get_encoding("cl100k_base")
    return _encoder


def count_tokens(text: str) -> int:
    return len(_get_encoder().encode(text))


def chunk_text(
    text: str,
    doc_id: str,
    min_tokens: int = 300,
    max_tokens: int = 800,
    overlap_ratio: float = 0.15,
) -> List[dict]:
    """
    Split text into chunks preserving section boundaries.
    Returns list of dicts with: id, content, metadata (chunk_index, token_count).
    """
    sections = _split_by_headers(text)

    chunks = []
    chunk_index = 0
    buffer = ""
    buffer_tokens = 0

    for section in sections:
        section_tokens = count_tokens(section)

        if section_tokens > max_tokens:
            if buffer.strip():
                flushed = _flush_buffer(buffer, doc_id, chunk_index, max_tokens, overlap_ratio)
                chunks.extend(flushed)
                chunk_index += len(flushed)
                buffer = ""
                buffer_tokens = 0
            sub_chunks = _split_large_section(section, doc_id, chunk_index, max_tokens, overlap_ratio)
            chunks.extend(sub_chunks)
            chunk_index += len(sub_chunks)
        elif buffer_tokens + section_tokens > max_tokens:
            if buffer.strip():
                chunks.append(_make_chunk(buffer.strip(), doc_id, chunk_index))
                chunk_index += 1
            overlap_text = _get_overlap(buffer, overlap_ratio)
            buffer = overlap_text + "\n" + section
            buffer_tokens = count_tokens(buffer)
        else:
            buffer = (buffer + "\n" + section).strip()
            buffer_tokens = count_tokens(buffer)

            if buffer_tokens >= min_tokens:
                chunks.append(_make_chunk(buffer, doc_id, chunk_index))
                chunk_index += 1
                overlap_text = _get_overlap(buffer, overlap_ratio)
                buffer = overlap_text
                buffer_tokens = count_tokens(buffer)

    if buffer.strip() and count_tokens(buffer.strip()) >= _MIN_FINAL_CHUNK_TOKENS:
        chunks.append(_make_chunk(buffer.strip(), doc_id, chunk_index))

    if not chunks and text.strip():
        chunks.append(_make_chunk(text.strip(), doc_id, 0))

    return chunks


def _split_by_headers(text: str) -> List[str]:
    lines = text.split("\n")
    sections = []
    current: List[str] = []

    for line in lines:
        if re.match(r"^#{1,3}\s+", line) and current:
            sections.append("\n".join(current))
            current = [line]
        else:
            current.append(line)

    if current:
        sections.append("\n".join(current))

    return [s for s in sections if s.strip()]


def _split_large_section(
    text: str,
    doc_id: str,
    start_index: int,
    max_tokens: int,
    overlap_ratio: float,
) -> List[dict]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks = []
    buffer = ""
    chunk_index = start_index

    for sentence in sentences:
        candidate = (buffer + " " + sentence).strip() if buffer else sentence
        if count_tokens(candidate) > max_tokens and buffer:
            chunks.append(_make_chunk(buffer, doc_id, chunk_index))
            chunk_index += 1
            overlap = _get_overlap(buffer, overlap_ratio)
            buffer = (overlap + " " + sentence).strip()
        else:
            buffer = candidate

    if buffer.strip():
        chunks.append(_make_chunk(buffer.strip(), doc_id, chunk_index))

    return chunks


def _flush_buffer(
    buffer: str,
    doc_id: str,
    start_index: int,
    max_tokens: int,
    overlap_ratio: float,
) -> List[dict]:
    if count_tokens(buffer) <= max_tokens:
        return [_make_chunk(buffer, doc_id, start_index)]
    return _split_large_section(buffer, doc_id, start_index, max_tokens, overlap_ratio)


def _get_overlap(text: str, ratio: float) -> str:
    encoder = _get_encoder()
    tokens = encoder.encode(text)
    overlap_count = int(len(tokens) * ratio)
    if overlap_count == 0:
        return ""
    overlap_tokens = tokens[-overlap_count:]
    return encoder.decode(overlap_tokens)


def _make_chunk(content: str, doc_id: str, index: int) -> dict:
    return {
        "id": f"{doc_id}::chunk::{index}",
        "content": content,
        "metadata": {
            "chunk_index": index,
            "token_count": count_tokens(content),
        },
    }
