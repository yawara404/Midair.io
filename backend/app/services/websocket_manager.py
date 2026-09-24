"""WebSocket 接続・ブロードキャスト管理。"""
import time
from typing import Any, Optional

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = {}
        self._handles: dict[WebSocket, str] = {}
        self._last_activity: dict[int, float] = {}

    async def connect(self, channel_id: int, websocket: WebSocket, handle: str) -> None:
        await websocket.accept()
        self._connections.setdefault(channel_id, set()).add(websocket)
        self._handles[websocket] = handle
        self.touch(channel_id)

    def disconnect(self, channel_id: int, websocket: WebSocket) -> None:
        self._handles.pop(websocket, None)
        conns = self._connections.get(channel_id)
        if conns is not None:
            conns.discard(websocket)
            if not conns:
                self._connections.pop(channel_id, None)

    async def broadcast(self, channel_id: int, message: dict[str, Any]) -> None:
        conns = list(self._connections.get(channel_id, set()))
        for ws in conns:
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(channel_id, ws)

    async def broadcast_all(self, message: dict[str, Any]) -> None:
        """全接続（全ステーション＋ロビー）へ配信する。周波数ステータス同期用。"""
        seen: set[int] = set()
        for channel_id in list(self._connections.keys()):
            for ws in list(self._connections.get(channel_id, set())):
                if id(ws) in seen:
                    continue
                seen.add(id(ws))
                try:
                    await ws.send_json(message)
                except Exception:
                    self.disconnect(channel_id, ws)

    def handle_of(self, websocket: WebSocket) -> Optional[str]:
        return self._handles.get(websocket)

    def channel_count(self, channel_id: int) -> int:
        return len(self._connections.get(channel_id, set()))

    def active_channels(self) -> list[int]:
        return list(self._connections.keys())

    def touch(self, channel_id: int) -> None:
        self._last_activity[channel_id] = time.time()

    def idle_seconds(self, channel_id: int) -> float:
        return time.time() - self._last_activity.get(channel_id, time.time())


manager = ConnectionManager()
