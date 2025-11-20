# app.py — Fully Agentic WA bot (single-send guard + inbound idempotency + robust onboarding)

import os, io, re, json, socket, uuid
from typing import Optional, Tuple, List, Dict, Any
from datetime import datetime, timezone, timedelta

import requests
import numpy as np
import cv2
from fastapi import FastAPI, Request, Query
from fastapi.responses import JSONResponse, PlainTextResponse
from dotenv import load_dotenv
from PIL import Image

# ---------- TZ ----------
try:
    import zoneinfo
    ZoneInfo = zoneinfo.ZoneInfo
except Exception:
    ZoneInfo = None

# ---------- ENV ----------
load_dotenv()
TOKEN     = os.getenv("WHATSAPP_TOKEN", "")
PHONE_ID  = os.getenv("WABA_PHONE_ID", os.getenv("WHATSAPP_PHONE_ID", ""))
VERIFY    = os.getenv("WHATSAPP_VERIFY_TOKEN", os.getenv("VERIFY_TOKEN", "verify_me"))
GRAPH     = os.getenv("GRAPH_BASE", "https://graph.facebook.com/v20.0")
TZ_REGION = os.getenv("TZ_REGION", "Asia/Jakarta")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    print("[WARN] OPENAI_API_KEY missing. This file requires it for agent control.")

PRINTER_TYPE    = os.getenv("PRINTER_TYPE", "none")  # zebra | file | none
PRINTER_ADDRESS = os.getenv("PRINTER_ADDRESS", "")   # "ip:9100"
LABEL_TITLE     = os.getenv("LABEL_TITLE", "MBG Kitchen")

# ---------- DB (SQLAlchemy) ----------
from sqlalchemy import (
    create_engine, MetaData, Table, Column, Integer, String, Text, DateTime,
    Index, select, func, ForeignKey
)
from sqlalchemy.exc import IntegrityError

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'scans.db')}")
engine_kwargs = {"future": True, "pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite:///"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
engine = create_engine(DATABASE_URL, **engine_kwargs)
metadata = MetaData()

# --- Master entities
items = Table(
    "items", metadata,
    Column("id", String, primary_key=True),   # BHN-xxxxx
    Column("name", String),
    Column("weight_grams", Integer),
    Column("unit", String),
    Column("created_at", DateTime, server_default=func.now()),
)
trays = Table(
    "trays", metadata,
    Column("id", String, primary_key=True),   # TRY-xxxxx
    Column("created_at", DateTime, server_default=func.now()),
)
tray_items = Table(
    "tray_items", metadata,
    Column("id", Integer, primary_key=True),
    Column("tray_id", String, ForeignKey("trays.id")),
    Column("item_id", String, ForeignKey("items.id")),
    Column("bound_by_number", String),
    Column("bound_at", DateTime, server_default=func.now()),
)
Index("ix_tray_items_tray", tray_items.c.tray_id)

# --- Event log
events = Table(
    "events", metadata,
    Column("id", Integer, primary_key=True),
    Column("ts_local", String, nullable=False),
    Column("from_number", String),
    Column("division", String),      # receiving/processing/packing/delivery/school_receipt
    Column("subject_type", String),  # item | tray
    Column("subject_id", String),    # BHN-xxxxx | TRY-xxxxx
    Column("message_text", Text),
    Column("duration_hms", String),  # HH:MM:SS
    Column("duration_seconds", Integer),
    Column("extra", Text),
    Column("created_at", DateTime, server_default=func.now()),
)
Index("ix_events_subject", events.c.subject_type, events.c.subject_id)

# --- Staff & onboarding
staffs = Table(
    "staffs", metadata,
    Column("phone", String, primary_key=True),  # E.164 without '+'
    Column("name", String, nullable=False),
    Column("division", String, nullable=False), # receiving/processing/packing/delivery/school_receipt
    Column("created_at", DateTime, server_default=func.now()),
)
registrations = Table(
    "registrations", metadata,
    Column("phone", String, primary_key=True),
    Column("state", String),       # ask_name | ask_division
    Column("temp_name", String),
    Column("created_at", DateTime, server_default=func.now()),
)

# --- Inbound idempotency (kill WA duplicate deliveries)
inbound_seen = Table(
    "inbound_seen", metadata,
    Column("id", String, primary_key=True),   # WhatsApp message.id
    Column("created_at", DateTime, server_default=func.now()),
)

metadata.create_all(engine)

# ---------- OpenAI ----------
from openai import OpenAI
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# ---------- Helpers ----------
DIV_CANON = {
    "receiving": "receiving", "penerimaan": "receiving",
    "processing": "processing", "pemrosesan": "processing", "proses": "processing",
    "packing": "packing", "pengemasan": "packing",
    "delivery": "delivery", "pengiriman": "delivery",
    "school_receipt": "school_receipt", "penerima manfaat": "school_receipt",
    "penerima": "school_receipt", "sekolah": "school_receipt",
}

def now_local_iso() -> str:
    dt_utc = datetime.now(tz=timezone.utc)
    tz = ZoneInfo(TZ_REGION) if ZoneInfo else datetime.now().astimezone().tzinfo
    return dt_utc.astimezone(tz).isoformat(timespec="seconds")

def parse_duration_hms(td: timedelta) -> Tuple[str, int]:
    sec = max(0, int(td.total_seconds()))
    h = sec // 3600; m = (sec % 3600) // 60; s = sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}", sec

def compute_duration(current_ts_iso: str, prev_ts_iso: Optional[str]) -> Tuple[str, int]:
    if not prev_ts_iso:
        return ("00:00:00", 0)
    try:
        cur = datetime.fromisoformat(current_ts_iso)
        prev = datetime.fromisoformat(prev_ts_iso)
        return parse_duration_hms(cur - prev)
    except Exception:
        return ("00:00:00", 0)

def canonical_division(text: str) -> Optional[str]:
    if not text: return None
    t = text.strip().lower()
    parts = re.findall(r"[a-zA-Z_]+", t)
    for p in parts:
        if p in DIV_CANON: return DIV_CANON[p]
    return DIV_CANON.get(t)

def is_item_id(s: str) -> bool: return s.upper().startswith("BHN-")
def is_tray_id(s: str) -> bool: return s.upper().startswith("TRY-")
def new_item_id() -> str: return "BHN-" + uuid.uuid4().hex[:8].upper()

def _jsonable(o):
    from datetime import datetime, date
    if isinstance(o, (datetime, date)): return o.isoformat()
    if isinstance(o, (bytes, bytearray)): return f"<{len(o)} bytes>"
    return str(o)

# ---------- WhatsApp ----------
def wa_url(): return f"{GRAPH}/{PHONE_ID}/messages"

def wa_send_text(to: str, body: str) -> Tuple[bool, str]:
    headers = {"Authorization": f"Bearer {TOKEN}"}
    data = {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": body}}
    try:
        r = requests.post(wa_url(), headers=headers, json=data, timeout=30)
        if not r.ok:
            print(f"[WA SEND ERROR] {r.status_code} {r.text}")
            return False, r.text
        return True, r.text
    except Exception as e:
        print(f"[WA SEND EXC] {e}")
        return False, str(e)

def get_media_url(media_id: str) -> str:
    headers = {"Authorization": f"Bearer {TOKEN}"}
    r = requests.get(f"{GRAPH}/{media_id}", headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()["url"]

def fetch_media(url: str) -> bytes:
    headers = {"Authorization": f"Bearer {TOKEN}"}
    r = requests.get(url, headers=headers, timeout=60)
    r.raise_for_status()
    return r.content

# ---------- QR decode ----------
try:
    from pyzbar.pyzbar import decode as zbar_decode
except Exception:
    zbar_decode = None

def decode_codes(img_bytes: bytes) -> List[str]:
    out = []
    if zbar_decode:
        try:
            pil = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            for obj in zbar_decode(pil):
                if obj.data:
                    s = obj.data.decode("utf-8", errors="ignore").strip()
                    if s and s not in out: out.append(s)
        except Exception:
            pass
    try:
        arr = np.frombuffer(img_bytes, np.uint8)
        cv_img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if cv_img is not None:
            data, _, _ = cv2.QRCodeDetector().detectAndDecode(cv_img)
            if data:
                s = data.strip()
                if s and s not in out: out.append(s)
    except Exception:
        pass
    return out

# ---------- DB helpers ----------
def db_get_staff(phone: str) -> Optional[dict]:
    with engine.connect() as c:
        row = c.execute(select(staffs).where(staffs.c.phone == phone).limit(1)).first()
        return dict(row._mapping) if row else None

def db_set_staff(phone: str, name: str, division: str):
    with engine.begin() as c:
        if c.execute(select(staffs.c.phone).where(staffs.c.phone == phone)).first():
            c.execute(staffs.update().where(staffs.c.phone == phone).values(name=name, division=division))
        else:
            c.execute(staffs.insert().values(phone=phone, name=name, division=division))

def db_get_reg(phone: str) -> Optional[dict]:
    with engine.connect() as c:
        row = c.execute(select(registrations).where(registrations.c.phone == phone)).first()
        return dict(row._mapping) if row else None

def db_set_reg(phone: str, state: str, temp_name: Optional[str] = None):
    with engine.begin() as c:
        if c.execute(select(registrations.c.phone).where(registrations.c.phone == phone)).first():
            c.execute(registrations.update().where(registrations.c.phone == phone).values(state=state, temp_name=temp_name))
        else:
            c.execute(registrations.insert().values(phone=phone, state=state, temp_name=temp_name))

def db_clear_reg(phone: str):
    with engine.begin() as c:
        c.execute(registrations.delete().where(registrations.c.phone == phone))

def db_insert_item(item_id: str, name: str, weight_g: int, unit: str = "g"):
    with engine.begin() as c:
        if not c.execute(select(items.c.id).where(items.c.id == item_id)).first():
            c.execute(items.insert().values(id=item_id, name=name, weight_grams=weight_g, unit=unit))

def db_insert_tray_if_needed(tray_id: str):
    with engine.begin() as c:
        if not c.execute(select(trays.c.id).where(trays.c.id == tray_id)).first():
            c.execute(trays.insert().values(id=tray_id))

def db_last_event(subject_type: str, subject_id: str, division: Optional[str] = None):
    with engine.connect() as c:
        stmt = select(events).where(events.c.subject_type == subject_type, events.c.subject_id == subject_id)
        if division:
            stmt = stmt.where(events.c.division == division)
        stmt = stmt.order_by(events.c.id.desc()).limit(1)
        row = c.execute(stmt).first()
        return dict(row._mapping) if row else None

def db_insert_event(ts_local: str, phone: str, division: str, subject_type: str, subject_id: str,
                    message_text: str, duration_hms: str, duration_sec: int, extra: dict):
    with engine.begin() as c:
        c.execute(events.insert().values(
            ts_local=ts_local, from_number=phone, division=division,
            subject_type=subject_type, subject_id=subject_id,
            message_text=message_text, duration_hms=duration_hms,
            duration_seconds=duration_sec, extra=json.dumps(extra or {})
        ))

def db_recent_processed_item(phone: str, window_min: int = 10) -> Optional[Tuple[str, str]]:
    now_iso = now_local_iso()
    with engine.connect() as c:
        ev = c.execute(
            select(events.c.subject_id, events.c.ts_local)
            .where(events.c.division == "processing", events.c.from_number == phone, events.c.subject_type == "item")
            .order_by(events.c.id.desc()).limit(1)
        ).first()
    if not ev: return None
    item_id, ts = ev
    try:
        d = datetime.fromisoformat(now_iso) - datetime.fromisoformat(ts)
        if d.total_seconds() > window_min * 60:
            return None
    except Exception:
        pass
    return (item_id, ts)

def mark_inbound_seen(mid: Optional[str]) -> bool:
    """Return True if this message-id was seen before (so caller should skip)."""
    if not mid:
        return False
    with engine.begin() as c:
        if c.execute(select(inbound_seen.c.id).where(inbound_seen.c.id == mid)).first():
            return True
        c.execute(inbound_seen.insert().values(id=mid))
        return False

# ---------- Printing ----------
def qr_link_for_item(item_id: str) -> str:
    return f"https://wa.me/6287727981162?text={item_id}"

def zpl_label(item_id: str, name: str, weight_g: int) -> str:
    link = qr_link_for_item(item_id); kg = weight_g / 1000.0
    return f"""^XA
^PW600
^LH0,0
^FO30,30^A0N,30,30^FD{LABEL_TITLE}^FS
^FO30,70^A0N,28,28^FDItem: {name}^FS
^FO30,105^A0N,28,28^FDWeight: {kg:.2f} kg^FS
^FO30,140^A0N,28,28^FDID: {item_id}^FS
^FO30,180^BQN,2,6
^FDQA,{link}^FS
^XZ
"""

def print_label(item_id: str, name: str, weight_g: int):
    if PRINTER_TYPE == "none":
        return
    zpl = zpl_label(item_id, name, weight_g)
    if PRINTER_TYPE == "zebra" and PRINTER_ADDRESS:
        host, port = PRINTER_ADDRESS.split(":")
        with socket.create_connection((host, int(port)), timeout=5) as s:
            s.sendall(zpl.encode("utf-8"))
    else:
        with open(f"label_{item_id}.zpl", "w", encoding="utf-8") as f:
            f.write(zpl)

# ---------- Agent Tools (implementations) ----------
def tool_send_text(phone: str, body: str) -> Dict[str, Any]:
    ok, resp = wa_send_text(phone, body); return {"ok": ok, "raw": resp}

def tool_get_staff(phone: str) -> Dict[str, Any]:
    return db_get_staff(phone) or {}

def tool_get_registration(phone: str) -> Dict[str, Any]:
    return db_get_reg(phone) or {}

def tool_set_registration(phone: str, state: str, temp_name: Optional[str] = None) -> Dict[str, Any]:
    db_set_reg(phone, state, temp_name); return {"ok": True}

def tool_clear_registration(phone: str) -> Dict[str, Any]:
    db_clear_reg(phone); return {"ok": True}

def tool_register_staff(phone: str, division_text: str, name: Optional[str] = None) -> Dict[str, Any]:
    """Name is optional; if missing, pull from registrations.temp_name."""
    if not name:
        reg = db_get_reg(phone) or {}
        name = (reg.get("temp_name") or "Staff").strip()
    div = canonical_division(division_text or "")
    if not div:
        return {"ok": False, "error": "invalid_division"}
    db_set_staff(phone, name, div)
    db_clear_reg(phone)
    return {"ok": True, "division": div, "name": name}

def tool_create_item(phone: str, name: str, weight_grams: int, unit: str, raw_text: str, ts_local: str) -> Dict[str, Any]:
    item_id = new_item_id()
    db_insert_item(item_id, name, int(weight_grams), unit or "g")
    db_insert_event(ts_local, phone, "receiving", "item", item_id, raw_text, "00:00:00", 0,
                    extra={"name": name, "weight_grams": int(weight_grams)})
    try: print_label(item_id, name, int(weight_grams))
    except Exception as e: print(f"[PRINT ERROR] {e}")
    link = qr_link_for_item(item_id)
    return {"ok": True, "item_id": item_id, "link": link,
            "reply": f"Receive with ID {item_id} has been added\nScan QR: {link}"}

def tool_route_scanned(phone: str, scanned_id: str, ts_local: str, stage: Optional[str] = None,
                       item_id: Optional[str] = None) -> Dict[str, Any]:
    staff = db_get_staff(phone) or {}
    if not stage:
        stage = staff.get("division") or "unknown"

    if is_item_id(scanned_id):
        if stage == "unknown": stage = "processing"
        prev = db_last_event("item", scanned_id, division="receiving")
        prev_ts = prev["ts_local"] if prev else None
        dur_hms, dur_sec = compute_duration(ts_local, prev_ts)
        db_insert_event(ts_local, phone, stage, "item", scanned_id, f"Scanned-{scanned_id}", dur_hms, dur_sec, extra={})
        return {"ok": True, "reply": f"{stage.capitalize()} with ID {scanned_id} has been added"}

    if is_tray_id(scanned_id):
        if stage == "unknown": stage = "packing"
        db_insert_tray_if_needed(scanned_id)

        if stage == "packing":
            bound = item_id
            if not bound:
                recent = db_recent_processed_item(phone, window_min=10)
                bound = recent[0] if recent else None
            prev_ts = None
            if bound:
                prev_proc = db_last_event("item", bound, division="processing")
                prev_ts = prev_proc["ts_local"] if prev_proc else None
            dur_hms, dur_sec = compute_duration(ts_local, prev_ts)
            with engine.begin() as c:
                c.execute(tray_items.insert().values(tray_id=scanned_id, item_id=bound, bound_by_number=phone))
            db_insert_event(ts_local, phone, "packing", "tray", scanned_id, f"Scanned-{scanned_id}", dur_hms, dur_sec,
                            extra={"bound_item": bound})
            return {"ok": True, "reply": f"Packing with ID {scanned_id} has been added"}

        if stage == "delivery":
            prev = db_last_event("tray", scanned_id, division="packing")
            prev_ts = prev["ts_local"] if prev else None
            dur_hms, dur_sec = compute_duration(ts_local, prev_ts)
            db_insert_event(ts_local, phone, "delivery", "tray", scanned_id, f"Scanned-{scanned_id}", dur_hms, dur_sec, extra={})
            return {"ok": True, "reply": f"Delivery with ID {scanned_id} has been added"}

        if stage == "school_receipt":
            prev = db_last_event("tray", scanned_id, division="delivery")
            prev_ts = prev["ts_local"] if prev else None
            dur_hms, dur_sec = compute_duration(ts_local, prev_ts)
            db_insert_event(ts_local, phone, "school_receipt", "tray", scanned_id, f"Scanned-{scanned_id}", dur_hms, dur_sec, extra={})
            return {"ok": True, "reply": f"School_receipt with ID {scanned_id} has been added"}

        db_insert_event(ts_local, phone, stage, "tray", scanned_id, f"Scanned-{scanned_id}", "00:00:00", 0, extra={})
        return {"ok": True, "reply": f"{stage.capitalize()} with ID {scanned_id} has been added"}

    return {"ok": False, "reply": "Format ID tidak dikenal. Gunakan BHN-xxxxx (item) atau TRY-xxxxx (tray)."}

def tool_decode_qr(media_id: str) -> Dict[str, Any]:
    try:
        url = get_media_url(media_id); img = fetch_media(url)
        texts = decode_codes(img)
        scanned = None
        for t in texts:
            mm = re.search(r"(?i)scanned-([A-Za-z0-9\-]+)", t)
            if mm: scanned = f"Scanned-{mm.group(1)}"; break
        return {"ok": True, "raw_texts": texts, "scanned_text": scanned}
    except Exception as e:
        print(f"[IMG ERROR] {e}")
        return {"ok": False, "raw_texts": [], "scanned_text": None}

# ---------- Tools schema exposed to agent ----------
TOOLS = [
    { "type":"function","function":{
        "name":"tool_send_text","description":"Send a WhatsApp text message to the user.",
        "parameters":{"type":"object","properties":{"phone":{"type":"string"},"body":{"type":"string"}},"required":["phone","body"]}
    }},
    { "type":"function","function":{
        "name":"tool_get_staff","description":"Fetch staff record by phone number; {} if not registered.",
        "parameters":{"type":"object","properties":{"phone":{"type":"string"}},"required":["phone"]}
    }},
    { "type":"function","function":{
        "name":"tool_get_registration","description":"Get onboarding state for a phone (ask_name/ask_division).",
        "parameters":{"type":"object","properties":{"phone":{"type":"string"}},"required":["phone"]}
    }},
    { "type":"function","function":{
        "name":"tool_set_registration","description":"Set onboarding state for a phone.",
        "parameters":{"type":"object","properties":{"phone":{"type":"string"},"state":{"type":"string"},"temp_name":{"type":"string"}},"required":["phone","state"]}
    }},
    { "type":"function","function":{
        "name":"tool_clear_registration","description":"Clear onboarding state.",
        "parameters":{"type":"object","properties":{"phone":{"type":"string"}},"required":["phone"]}
    }},
    { "type":"function","function":{
        "name":"tool_register_staff","description":"Register staff; if 'name' omitted, use temp_name from registrations.",
        "parameters":{"type":"object","properties":{
            "phone":{"type":"string"},"division_text":{"type":"string"},"name":{"type":"string"}
        },"required":["phone","division_text"]}
    }},
    { "type":"function","function":{
        "name":"tool_create_item","description":"Create item and log receiving; returns user-facing reply.",
        "parameters":{"type":"object","properties":{
            "phone":{"type":"string"},"name":{"type":"string"},"weight_grams":{"type":"integer"},"unit":{"type":"string"},
            "raw_text":{"type":"string"},"ts_local":{"type":"string"}
        },"required":["phone","name","weight_grams","unit","raw_text","ts_local"]}
    }},
    { "type":"function","function":{
        "name":"tool_route_scanned","description":"Route Scanned-* IDs and log events.",
        "parameters":{"type":"object","properties":{
            "phone":{"type":"string"},"scanned_id":{"type":"string"},"ts_local":{"type":"string"},
            "stage":{"type":"string"},"item_id":{"type":"string"}
        },"required":["phone","scanned_id","ts_local"]}
    }},
    { "type":"function","function":{
        "name":"tool_decode_qr","description":"Decode a WhatsApp image to possible QR payloads; returns first 'Scanned-*' if found.",
        "parameters":{"type":"object","properties":{"media_id":{"type":"string"}},"required":["media_id"]}
    }},
]

# ---------- System prompt ----------
SYSTEM_PROMPT = """
You are the MBG Kitchen WhatsApp Agent. Control the bot ONLY via tools.
ALWAYS send exactly one final user-visible message via tool_send_text per inbound message.

Onboarding (agentic):
- Call tool_get_staff(phone). If empty:
  - Call tool_get_registration(phone).
  - If no state: tool_set_registration(ask_name) -> tool_send_text("Nomor Anda belum terdaftar. Siapa nama Anda?") -> STOP.
  - If state=ask_name and user sent non-Scanned text: tool_set_registration(ask_division, temp_name=<name>) ->
    tool_send_text("Terima kasih. Anda dari divisi apa? Pilihan: Penerimaan / Pemrosesan / Packing / Pengiriman / Penerima manfaat") -> STOP.
  - If state=ask_division and user replies: call tool_register_staff(phone, division_text=user_text). If invalid_division, ask again and STOP.
    On success: tool_clear_registration -> tool_send_text("Terima kasih, {name}. Anda terdaftar sebagai divisi *{division}*. Silakan kirim ulang perintah/scan Anda.") -> STOP.

Routing (registered):
- If message_type == "image": tool_decode_qr; if a 'Scanned-*' ID appears, tool_route_scanned; else tool_send_text("Gambar diterima, namun tidak menemukan QR yang valid.").
- If text starts with 'Scanned-':
    * If BHN-* : tool_route_scanned (stage defaults to 'processing').
    * If TRY-* : tool_route_scanned (stage defaults from staff division: packing/delivery/school_receipt).
- Otherwise free text:
    * If staff division == receiving: parse inline (e.g., 'bahan: daging 500 g', 'ayam 12 kg'); if weight missing, ask to include weight; else tool_create_item and forward its reply.
    * Else: tool_send_text("Gunakan QR (Scanned-...) untuk tahap ini, atau minta nomor penerimaan mencatat bahan.").

Be concise and deterministic. After you send a prompt/question during onboarding, STOP.
"""

# ---------- Agent loop (with single-send guard) ----------
def run_agent(phone: str, mtype: str, text: Optional[str], media_id: Optional[str], ts_local: str):
    if not client:
        wa_send_text(phone, "Server misconfigured: OPENAI_API_KEY is missing.")
        return

    user_payload = {"phone": phone, "message_type": mtype, "text": text or "", "media_id": media_id or "", "ts_local": ts_local}
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}
    ]

    sent_reply = False  # <— single-send guard

    for _ in range(12):
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0
        )
        msg = resp.choices[0].message
        tool_calls = getattr(msg, "tool_calls", None)

        if tool_calls:
            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [{
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments or "{}"}
                } for tc in tool_calls]
            })

            for tc in tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except Exception:
                    args = {}

                if name == "tool_send_text":
                    if sent_reply:
                        # ignore any extra sends in the same turn
                        result = {"ok": True, "ignored": True}
                    else:
                        result = tool_send_text(args["phone"], args["body"])
                        sent_reply = True
                elif name == "tool_get_staff":
                    result = tool_get_staff(args["phone"])
                elif name == "tool_get_registration":
                    result = tool_get_registration(args["phone"])
                elif name == "tool_set_registration":
                    result = tool_set_registration(args["phone"], args["state"], args.get("temp_name"))
                elif name == "tool_clear_registration":
                    result = tool_clear_registration(args["phone"])
                elif name == "tool_register_staff":
                    result = tool_register_staff(args["phone"], args.get("division_text",""), args.get("name"))
                elif name == "tool_create_item":
                    result = tool_create_item(args["phone"], args["name"], int(args["weight_grams"]),
                                              args.get("unit","g"), args.get("raw_text",""), args["ts_local"])
                elif name == "tool_route_scanned":
                    result = tool_route_scanned(args["phone"], args["scanned_id"], args["ts_local"],
                                                args.get("stage"), args.get("item_id"))
                elif name == "tool_decode_qr":
                    result = tool_decode_qr(args["media_id"])
                else:
                    result = {"ok": False, "error": f"unknown_tool:{name}"}

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, ensure_ascii=False, default=_jsonable)
                })

            # If we've already sent a user-visible reply, end this turn.
            if sent_reply:
                break

            continue

        if msg.content and not sent_reply:
            wa_send_text(phone, msg.content)
            sent_reply = True
        break

# ---------- FastAPI ----------
app = FastAPI(title="MBG WA Agent (Fully Agentic + Single-Send + Idempotent)")

@app.get("/webhook", response_class=PlainTextResponse)
def verify(hub_mode: str = Query(None, alias="hub.mode"),
           hub_challenge: str = Query(None, alias="hub.challenge"),
           hub_token: str = Query(None, alias="hub.verify_token")):
    if hub_mode == "subscribe" and hub_token == VERIFY:
        return hub_challenge or ""
    return PlainTextResponse("Forbidden", 403)

@app.post("/webhook")
async def webhook(request: Request):
    try:
        payload = await request.json()
        print("[WEBHOOK RECEIVED]")
    except Exception:
        return JSONResponse({"status":"invalid_json"}, status_code=200)

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
                        # duplicate delivery — skip entirely
                        continue

                    phone = msg.get("from")
                    if not phone: 
                        continue
                    mtype = msg.get("type")
                    ts_local = now_local_iso()

                    text = None; media_id = None
                    if mtype == "text":
                        text = (msg.get("text", {}) or {}).get("body", "")
                    elif mtype == "image":
                        media_id = msg["image"]["id"]

                    run_agent(phone, mtype, text, media_id, ts_local)

    except Exception as e:
        print(f"[ERROR] webhook: {e}")

    return JSONResponse({"status":"ok"})

# ---------- Debug ----------
@app.get("/healthz", response_class=PlainTextResponse)
def healthz():
    return f"OK GRAPH={GRAPH} PHONE_ID={PHONE_ID} DB={DATABASE_URL} OPENAI={'yes' if OPENAI_API_KEY else 'no'}"

@app.get("/debug/ping", response_class=PlainTextResponse)
def debug_ping(to: str, text: str = "hello from agentic bot"):
    ok, resp = wa_send_text(to, text)
    return f"ok={ok}\nresp={resp}"

# ---------- Local run ----------
if __name__ == "__main__":
    import uvicorn
    print(f"[INFO] DB={DATABASE_URL}")
    print(f"[INFO] GRAPH={GRAPH} PHONE_ID={PHONE_ID}")
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=False)
