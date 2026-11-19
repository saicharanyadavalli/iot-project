"""WebSocket Connection and Event Broadcast Manager.
Maintains active client connections, dispatches real-time event envelopes,
and handles graceful disconnects and heartbeats.
"""

from __future__ import annotations
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Set, Dict, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Thread-safe WebSocket broadcaster supporting client pools and structured event streaming."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """Accept connection and add to pool."""
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)
        logger.info("WebSocket client connected. Active count: %d", len(self.active_connections))

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove connection from pool."""
        async with self._lock:
            self.active_connections.discard(websocket)
        logger.info("WebSocket client disconnected. Active count: %d", len(self.active_connections))

    async def broadcast_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Broadcast a versioned, structured event envelope to all connected clients."""
        envelope = {
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }
        payload = json.dumps(envelope)

        dead_connections: Set[WebSocket] = set()
        async with self._lock:
            connections = list(self.active_connections)

        for conn in connections:
            try:
                await conn.send_text(payload)
            except Exception as e:
                logger.debug("Failed sending to client: %s", e)
                dead_connections.add(conn)

        if dead_connections:
            async with self._lock:
                self.active_connections.difference_update(dead_connections)

    def broadcast_sync(self, event_type: str, data: Dict[str, Any], loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        """Thread-safe bridge to broadcast from synchronous threads (e.g. SerialReader)."""
        target_loop = loop
        if target_loop is None:
            try:
                target_loop = asyncio.get_running_loop()
            except RuntimeError:
                pass

        if target_loop and target_loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast_event(event_type, data), target_loop)


ws_manager = WebSocketManager()
