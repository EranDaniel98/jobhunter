import json

import structlog
from fastapi import WebSocket

logger = structlog.get_logger()


class ConnectionManager:
    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, candidate_id: str, websocket: WebSocket):
        await websocket.accept()
        if candidate_id not in self._connections:
            self._connections[candidate_id] = []
        self._connections[candidate_id].append(websocket)
        logger.info("ws_connected", candidate_id=candidate_id)

    async def disconnect(self, candidate_id: str, websocket: WebSocket):
        if candidate_id in self._connections:
            self._connections[candidate_id].remove(websocket)
            if not self._connections[candidate_id]:
                del self._connections[candidate_id]
        logger.info("ws_disconnected", candidate_id=candidate_id)

    async def broadcast(self, candidate_id: str, event_type: str, payload: dict):
        if candidate_id not in self._connections:
            return
        message = json.dumps({"type": event_type, "data": payload})
        dead = []
        for ws in self._connections[candidate_id]:
            try:
                await ws.send_text(message)
            except Exception as e:
                logger.debug("ws_send_failed", candidate_id=candidate_id, error=str(e))
                dead.append(ws)
        for ws in dead:
            self._connections[candidate_id].remove(ws)


ws_manager = ConnectionManager()
