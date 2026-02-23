from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.infrastructure.websocket_manager import ws_manager
from app.utils.security import decode_token

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    # Authenticate via JWT
    try:
        payload = decode_token(token)
        candidate_id = payload.get("sub")
        if not candidate_id:
            await websocket.close(code=4001)
            return
    except Exception:
        await websocket.close(code=4001)
        return

    await ws_manager.connect(candidate_id, websocket)
    try:
        while True:
            await websocket.receive_text()  # keep-alive, ignore client messages
    except WebSocketDisconnect:
        await ws_manager.disconnect(candidate_id, websocket)
