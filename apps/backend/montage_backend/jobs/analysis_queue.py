from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from montage_backend.jobs.import_queue import ImportJobQueue


@dataclass(order=True)
class AnalysisQueueItem:
    sort_key: tuple[int, str, int]
    project_id: str = field(compare=False)
    media_id: str = field(compare=False)
    module_id: str = field(compare=False)
    job_id: str = field(compare=False)
    force: bool = field(compare=False, default=False)

    @classmethod
    def create(
        cls,
        *,
        project_id: str,
        media_id: str,
        module_id: str,
        job_id: str,
        priority: int,
        created_at: str,
        sequence: int,
        force: bool = False,
    ) -> AnalysisQueueItem:
        return cls(
            sort_key=(-priority, created_at, sequence),
            project_id=project_id,
            media_id=media_id,
            module_id=module_id,
            job_id=job_id,
            force=force,
        )


ExecuteFn = Callable[[AnalysisQueueItem], Awaitable[None]]


class AnalysisJobQueue:
    """Prioritized background queue for analysis jobs with pause/resume support."""

    def __init__(self, max_workers: int, execute: ExecuteFn) -> None:
        self._worker_pool = ImportJobQueue(max_workers=max_workers)
        self._execute = execute
        self._queue: asyncio.PriorityQueue[AnalysisQueueItem] = asyncio.PriorityQueue()
        self._paused_projects: set[str] = set()
        self._project_resume_events: dict[str, asyncio.Event] = {}
        self._worker_tasks: list[asyncio.Task[None]] = []
        self._sequence = 0
        self._pending_keys: set[str] = set()
        self._in_flight_keys: set[str] = set()
        self._started = False

    @property
    def max_workers(self) -> int:
        return self._worker_pool.max_workers

    @property
    def active_workers(self) -> int:
        return self._worker_pool.active_count

    @property
    def pending_count(self) -> int:
        return self._queue.qsize()

    @property
    def in_flight_count(self) -> int:
        return len(self._in_flight_keys)

    def is_project_paused(self, project_id: str) -> bool:
        return project_id in self._paused_projects

    def is_queued_or_running(self, key: str) -> bool:
        return key in self._pending_keys or key in self._in_flight_keys

    def ensure_started(self, dispatcher_count: int = 1) -> None:
        if self._started:
            return
        self._started = True
        for _ in range(max(1, dispatcher_count)):
            self._worker_tasks.append(asyncio.create_task(self._dispatcher_loop()))

    async def enqueue(
        self,
        *,
        project_id: str,
        media_id: str,
        module_id: str,
        job_id: str,
        priority: int,
        created_at: str,
        force: bool = False,
    ) -> None:
        key = f"{media_id}:{module_id}"
        if key in self._pending_keys or key in self._in_flight_keys:
            return
        self._sequence += 1
        item = AnalysisQueueItem.create(
            project_id=project_id,
            media_id=media_id,
            module_id=module_id,
            job_id=job_id,
            priority=priority,
            created_at=created_at,
            sequence=self._sequence,
            force=force,
        )
        self._pending_keys.add(key)
        await self._queue.put(item)

    async def _dispatcher_loop(self) -> None:
        while True:
            item = await self._queue.get()
            key = self._item_key(item)
            self._pending_keys.discard(key)
            try:
                await self._wait_if_project_paused(item.project_id)
                self._in_flight_keys.add(key)
                try:
                    await self._worker_pool.run(self._execute(item))
                finally:
                    self._in_flight_keys.discard(key)
            finally:
                self._queue.task_done()

    async def _wait_if_project_paused(self, project_id: str) -> None:
        while project_id in self._paused_projects:
            event = self._project_resume_events.setdefault(project_id, asyncio.Event())
            event.clear()
            await event.wait()

    def pause_project(self, project_id: str) -> None:
        self._paused_projects.add(project_id)

    def resume_project(self, project_id: str) -> None:
        self._paused_projects.discard(project_id)
        event = self._project_resume_events.setdefault(project_id, asyncio.Event())
        event.set()

    @staticmethod
    def _item_key(item: AnalysisQueueItem) -> str:
        return f"{item.media_id}:{item.module_id}"
