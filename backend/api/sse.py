import asyncio
import json
from typing import Optional

from fastapi import APIRouter, Query, HTTPException
from starlette.responses import StreamingResponse

from backend.utils.auth import decode_access_token, is_superadmin
from jose import JWTError

router = APIRouter()

# Connected SSE clients, each tagged with the kitchen they listen on.
# A client with kitchen_id=None listens on every kitchen (superadmin).
_clients: list[tuple[asyncio.Queue, Optional[int]]] = []


async def broadcast(event_type: str, data: dict):
    """Broadcast an event. If `data` contains `kitchen_id`, only clients
    subscribed to that kitchen (or the all-kitchens firehose) receive it."""
    msg = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
    event_kitchen = data.get("kitchen_id") if isinstance(data, dict) else None
    for q, client_kid in list(_clients):
        if client_kid is not None and event_kitchen is not None and client_kid != event_kitchen:
            continue
        try:
            q.put_nowait(msg)
        except asyncio.QueueFull:
            pass


async def _event_generator(queue: asyncio.Queue, kitchen_id: Optional[int]):
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
        _clients[:] = [(q, k) for q, k in _clients if q is not queue]


@router.get("/stream")
async def sse_stream(
    token: Optional[str] = Query(None),
    kitchen_id: Optional[int] = Query(None),
):
    """SSE. EventSource can't set headers, so auth + kitchen come as query params."""
    if not token:
        raise HTTPException(401, "Missing token")

    try:
        payload = decode_access_token(token)
        if not payload.get("sub"):
            raise HTTPException(401, "Invalid token")
    except JWTError:
        raise HTTPException(401, "Invalid or expired token")

    fake_user = {
        "role": payload.get("role"),
        "kitchen_ids": payload.get("kitchen_ids") or [],
        "active_kitchen_id": payload.get("active_kitchen_id"),
    }

    # Resolve which kitchen this stream listens on.
    resolved_kid: Optional[int] = kitchen_id if kitchen_id is not None else fake_user["active_kitchen_id"]

    if resolved_kid is not None and not is_superadmin(fake_user):
        if resolved_kid not in fake_user["kitchen_ids"]:
            raise HTTPException(403, "You do not have access to this kitchen")

    queue = asyncio.Queue(maxsize=50)
    _clients.append((queue, resolved_kid))

    return StreamingResponse(
        _event_generator(queue, resolved_kid),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
