async def run_ingestion(*args, **kwargs):
	from .pipeline import run_ingestion as _run_ingestion

	return await _run_ingestion(*args, **kwargs)


async def ingest_file(*args, **kwargs):
	from .pipeline import ingest_file as _ingest_file

	return await _ingest_file(*args, **kwargs)


async def delete_knowledge(*args, **kwargs):
	from .pipeline import delete_knowledge as _delete_knowledge

	return await _delete_knowledge(*args, **kwargs)


__all__ = ["run_ingestion", "ingest_file", "delete_knowledge"]
