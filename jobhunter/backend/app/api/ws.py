import structlog
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.infrastructure.redis_client import redis_safe_get
from app.infrastructure.websocket_manager import ws_manager
from app.utils.security import decode_token

router = APIRouter()
logger = structlog.get_logger()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    # Authenticate via JWT
    try:
        payload = decode_token(token)
        candidate_id = payload.get("sub")
        if not candidate_id:
            await websocket.close(code=4001)
            return
        jti = payload.get("jti")
        if jti and await redis_safe_get(f"token:blacklist:{jti}"):
            await websocket.close(code=4003)
            return
    except Exception as e:
        logger.warning("ws_auth_failed", error=str(e))
        await websocket.close(code=4001)
        return

    await ws_manager.connect(candidate_id, websocket)
    try:
        while True:
            await websocket.receive_text()  # keep-alive, ignore client messages
    except WebSocketDisconnect:
        await ws_manager.disconnect(candidate_id, websocket)
