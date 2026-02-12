from fastapi import Request, Query, Header, APIRouter
from fastapi.responses import JSONResponse, PlainTextResponse
from backend.core.config import VERIFY
from backend.services.agent import _jsonable
import json
from backend.services.agent import run_agent
from backend.core.database import mark_inbound_seen
from backend.utils.datetime_helpers import now_local_iso

router = APIRouter()

@router.get("/webhook", response_class=PlainTextResponse)
# def verify(
#     hub_mode: str = Query(None, alias="hub.mode"),
#     hub_challenge: str = Query(None, alias="hub.challenge"),
#     hub_token: str = Query(None, alias="hub.verify_token"),
# ):
def verify(request: Request):
    qp = dict(request.query_params)

    hub_mode = (qp.get("hub.mode") or "").strip()
    hub_token = (qp.get("hub.verify_token") or "").strip()
    hub_challenge = qp.get("hub.challenge") or ""
    
    print("[WEBHOOK] RAW query_params =", qp)
    print("[WEBHOOK] VERIFY repr =", repr(VERIFY))
    print("[WEBHOOK] hub_token repr =", repr(hub_token))
    print("[WEBHOOK] hub_mode repr =", repr(hub_mode))


    if hub_mode == "subscribe" and hub_token == VERIFY:
        return hub_challenge or ""
    return PlainTextResponse("Forbidden", status_code=403)

@router.post("/webhook")
async def webhook(request: Request):
    try:
        payload = await request.json()
        print("[WEBHOOK RECEIVED]")
    except Exception:
        return JSONResponse({"status": "invalid_json"}, status_code=200)

    try:
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})

                # Log statuses
                for st in value.get("statuses", []):
                    try:
                        print("[WA STATUS]", json.dumps(st, ensure_ascii=False, default=_jsonable))
                    except Exception:
                        print("[WA STATUS]", st)

                for msg in value.get("messages", []):
                    mid = msg.get("id")
                    if mark_inbound_seen(mid):
                        continue  # duplicate delivery

                    phone = msg.get("from")
                    if not phone:
                        continue
                    mtype = msg.get("type")
                    ts_local = now_local_iso()

                    text = None
                    media_id = None
                    if mtype == "text":
                        text = (msg.get("text", {}) or {}).get("body", "")
                    elif mtype == "image":
                        media_id = msg["image"]["id"]

                    run_agent(phone, mtype, text, media_id, ts_local)

    except Exception as e:
        print(f"[ERROR] webhook: {e}")

    return JSONResponse({"status": "ok"})
