import asyncio
import json
from typing import Optional

from fastapi import APIRouter, Query, HTTPException
from starlette.responses import StreamingResponse

from backend.utils.auth import decode_access_token
from jose import JWTError

router = APIRouter()

# Connected SSE clients
_clients: list[asyncio.Queue] = []


async def broadcast(event_type: str, data: dict):
    """Send an event to all connected SSE clients."""
    msg = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
    for q in list(_clients):
        try:
            q.put_nowait(msg)
        except asyncio.QueueFull:
            pass


async def _event_generator(queue: asyncio.Queue):
    """Yields SSE events from the queue + periodic pings."""
    try:
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield msg
            except asyncio.TimeoutError:
                yield "event: ping\ndata: {}\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        if queue in _clients:
            _clients.remove(queue)


@router.get("/stream")
async def sse_stream(token: Optional[str] = Query(None)):
    """SSE endpoint. Pass JWT as query param since EventSource can't set headers."""
    if not token:
        raise HTTPException(401, "Missing token")

    try:
        payload = decode_access_token(token)
        if not payload.get("sub"):
            raise HTTPException(401, "Invalid token")
    except JWTError:
        raise HTTPException(401, "Invalid or expired token")

    queue = asyncio.Queue(maxsize=50)
    _clients.append(queue)

    return StreamingResponse(
        _event_generator(queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
