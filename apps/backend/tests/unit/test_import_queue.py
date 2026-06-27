from __future__ import annotations

import asyncio

import pytest

from montage_backend.jobs.import_queue import ImportJobQueue


@pytest.mark.asyncio
async def test_import_queue_limits_concurrency() -> None:
    queue = ImportJobQueue(max_workers=2)
    active = 0
    peak = 0
    lock = asyncio.Lock()

    async def job() -> None:
        nonlocal active, peak
        async with lock:
            active += 1
            peak = max(peak, active)
        await asyncio.sleep(0.05)
        async with lock:
            active -= 1

    await asyncio.gather(*(queue.run(job()) for _ in range(6)))
    assert peak <= 2
    assert queue.max_workers == 2
