from __future__ import annotations

import asyncio

import pytest

from montage_backend.jobs.analysis_queue import AnalysisJobQueue


@pytest.mark.asyncio
async def test_analysis_queue_runs_jobs_with_concurrency_limit() -> None:
    completed: list[str] = []
    active = 0
    peak = 0
    lock = asyncio.Lock()

    async def execute(item) -> None:
        nonlocal active, peak
        async with lock:
            active += 1
            peak = max(peak, active)
        await asyncio.sleep(0.03)
        completed.append(item.module_id)
        async with lock:
            active -= 1

    queue = AnalysisJobQueue(max_workers=2, execute=execute)
    queue.ensure_started()

    for index in range(4):
        await queue.enqueue(
            project_id="p1",
            media_id=f"m{index}",
            module_id="scene",
            job_id=f"j{index}",
            priority=0,
            created_at=f"2026-01-0{index}",
        )

    await asyncio.sleep(0.2)
    assert len(completed) == 4
    assert peak <= 2


@pytest.mark.asyncio
async def test_analysis_queue_prioritizes_higher_priority_jobs() -> None:
    order: list[str] = []

    async def execute(item) -> None:
        order.append(item.module_id)

    queue = AnalysisJobQueue(max_workers=1, execute=execute)
    queue.ensure_started()

    await queue.enqueue(
        project_id="p1",
        media_id="m1",
        module_id="low",
        job_id="j1",
        priority=1,
        created_at="2026-01-03",
    )
    await queue.enqueue(
        project_id="p1",
        media_id="m2",
        module_id="high",
        job_id="j2",
        priority=100,
        created_at="2026-01-01",
    )

    await asyncio.sleep(0.05)
    assert order[0] == "high"


@pytest.mark.asyncio
async def test_analysis_queue_project_pause_blocks_dispatch() -> None:
    started: list[str] = []

    async def execute(item) -> None:
        started.append(item.module_id)

    queue = AnalysisJobQueue(max_workers=1, execute=execute)
    queue.pause_project("p1")
    queue.ensure_started()

    await queue.enqueue(
        project_id="p1",
        media_id="m1",
        module_id="scene",
        job_id="j1",
        priority=10,
        created_at="2026-01-01",
    )

    await asyncio.sleep(0.05)
    assert started == []

    queue.resume_project("p1")
    await asyncio.sleep(0.05)
    assert started == ["scene"]
