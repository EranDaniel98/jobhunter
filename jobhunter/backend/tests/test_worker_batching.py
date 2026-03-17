
import pytest


def test_chunk_list():
    from app.worker import _chunk_list
    items = list(range(25))
    chunks = _chunk_list(items, 10)
    assert len(chunks) == 3
    assert chunks[0] == list(range(10))
    assert chunks[1] == list(range(10, 20))
    assert chunks[2] == list(range(20, 25))


def test_chunk_list_empty():
    from app.worker import _chunk_list
    assert _chunk_list([], 10) == []


def test_chunk_list_exact_size():
    from app.worker import _chunk_list
    assert _chunk_list([1, 2, 3], 3) == [[1, 2, 3]]


@pytest.mark.asyncio
async def test_process_chunk_error_isolation():
    from app.worker import _process_chunk

    call_count = 0

    async def processor(item_id):
        nonlocal call_count
        call_count += 1
        if item_id == "fail":
            raise ValueError("Intentional failure")
        return f"ok:{item_id}"

    results = await _process_chunk(
        items=["a", "fail", "c"],
        processor=processor,
        concurrency=5,
        job_name="test",
    )
    assert call_count == 3
    assert results["succeeded"] == 2
    assert results["failed"] == 1
