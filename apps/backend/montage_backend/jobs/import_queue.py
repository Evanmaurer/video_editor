from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any, TypeVar

T = TypeVar("T")


class ImportJobQueue:
    """Limits concurrent media import/processing jobs to control CPU usage."""

    def __init__(self, max_workers: int = 2) -> None:
        self._max_workers = max(1, max_workers)
        self._semaphore = asyncio.Semaphore(self._max_workers)
        self._active_count = 0

    @property
    def max_workers(self) -> int:
        return self._max_workers

    @property
    def active_count(self) -> int:
        return self._active_count

    def set_max_workers(self, max_workers: int) -> None:
        self._max_workers = max(1, max_workers)
        self._semaphore = asyncio.Semaphore(self._max_workers)

    async def run(self, coro: Coroutine[Any, Any, T] | Callable[[], Awaitable[T]]) -> T:
        async with self._semaphore:
            self._active_count += 1
            try:
                if asyncio.iscoroutine(coro):
                    return await coro
                return await coro()
            finally:
                self._active_count -= 1
