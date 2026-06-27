from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from montage_backend.logging import get_logger

logger = get_logger(__name__)

BroadcastHandler = Callable[[dict], Awaitable[None] | None]


class WebSocketHub:
    """Broadcast JSON events to connected WebSocket clients."""

    def __init__(self) -> None:
        self._connections: set[object] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: object) -> None:
        async with self._lock:
            self._connections.add(websocket)

    async def disconnect(self, websocket: object) -> None:
        async with self._lock:
            self._connections.discard(websocket)

    async def broadcast(self, event: dict) -> None:
        async with self._lock:
            targets = list(self._connections)

        stale: list[object] = []
        for websocket in targets:
            try:
                send = getattr(websocket, "send_json", None)
                if send is None:
                    stale.append(websocket)
                    continue
                await send(event)
            except Exception:
                stale.append(websocket)

        if stale:
            async with self._lock:
                for websocket in stale:
                    self._connections.discard(websocket)

    @property
    def connection_count(self) -> int:
        return len(self._connections)


ws_hub = WebSocketHub()
