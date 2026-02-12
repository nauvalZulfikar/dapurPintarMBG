from typing import Optional
import json
from backend.core.config import OPENAI_API_KEY
from backend.services.whatsapp import wa_send_text
from backend.tools.utility_tools import tool_send_text, tool_decode_qr
from backend.tools.staff_tools import tool_get_staff, tool_get_registration, tool_set_registration, tool_clear_registration, tool_register_staff
from backend.tools.item_tools import tool_create_item, tool_route_scanned 

# ---------- OpenAI ----------
from openai import OpenAI
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

def _jsonable(o):
    from datetime import datetime as _dt, date as _date
    if isinstance(o, (_dt, _date)):
        return o.isoformat()
    if isinstance(o, (bytes, bytearray)):
        return f"<{len(o)} bytes>"
    return str(o)

# ---------- Tools schema exposed to agent ----------
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "tool_send_text",
            "description": "Send a WhatsApp text message to the user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["phone", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tool_get_staff",
            "description": "Fetch staff record by phone number; {} if not registered.",
            "parameters": {
                "type": "object",
                "properties": {"phone": {"type": "string"}},
                "required": ["phone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tool_get_registration",
            "description": "Get onboarding state for a phone (ask_name/ask_division).",
            "parameters": {
                "type": "object",
                "properties": {"phone": {"type": "string"}},
                "required": ["phone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tool_set_registration",
            "description": "Set onboarding state for a phone.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {"type": "string"},
                    "state": {"type": "string"},
                    "temp_name": {"type": "string"},
                },
                "required": ["phone", "state"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tool_clear_registration",
            "description": "Clear onboarding state.",
            "parameters": {
                "type": "object",
                "properties": {"phone": {"type": "string"}},
                "required": ["phone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tool_register_staff",
            "description": "Register staff; if 'name' omitted, use temp_name from registrations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {"type": "string"},
                    "division_text": {"type": "string"},
                    "name": {"type": "string"},
                },
                "required": ["phone", "division_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tool_create_item",
            "description": "Create item and log receiving; returns user-facing reply.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {"type": "string"},
                    "name": {"type": "string"},
                    "weight_grams": {"type": "integer"},
                    "unit": {"type": "string"},
                    "raw_text": {"type": "string"},
                    "ts_local": {"type": "string"},
                },
                "required": ["phone", "name", "weight_grams", "unit", "raw_text", "ts_local"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tool_route_scanned",
            "description": "Route Scanned-* IDs and log events.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {"type": "string"},
                    "scanned_id": {"type": "string"},
                    "ts_local": {"type": "string"},
                    "stage": {"type": "string"},
                    "item_id": {"type": "string"},
                },
                "required": ["phone", "scanned_id", "ts_local"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tool_decode_qr",
            "description": "Decode a WhatsApp image to possible QR payloads; returns first 'Scanned-*' if found.",
            "parameters": {
                "type": "object",
                "properties": {"media_id": {"type": "string"}},
                "required": ["media_id"],
            },
        },
    },
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

    user_payload = {
        "phone": phone,
        "message_type": mtype,
        "text": text or "",
        "media_id": media_id or "",
        "ts_local": ts_local,
    }
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
    ]

    sent_reply = False  # <— single-send guard

    for _ in range(12):
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0,
        )
        msg = resp.choices[0].message
        tool_calls = getattr(msg, "tool_calls", None)

        if tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments or "{}",
                            },
                        }
                        for tc in tool_calls
                    ],
                }
            )

            for tc in tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except Exception:
                    args = {}

                if name == "tool_send_text":
                    if sent_reply:
                        result = {"ok": True, "ignored": True}
                    else:
                        result = tool_send_text(args["phone"], args["body"])
                        sent_reply = True
                elif name == "tool_get_staff":
                    result = tool_get_staff(args["phone"])
                elif name == "tool_get_registration":
                    result = tool_get_registration(args["phone"])
                elif name == "tool_set_registration":
                    result = tool_set_registration(
                        args["phone"], args["state"], args.get("temp_name")
                    )
                elif name == "tool_clear_registration":
                    result = tool_clear_registration(args["phone"])
                elif name == "tool_register_staff":
                    result = tool_register_staff(
                        args["phone"],
                        args.get("division_text", ""),
                        args.get("name"),
                    )
                elif name == "tool_create_item":
                    result = tool_create_item(
                        args["phone"],
                        args["name"],
                        int(args["weight_grams"]),
                        args.get("unit", "g"),
                        args.get("raw_text", ""),
                        args["ts_local"],
                    )
                elif name == "tool_route_scanned":
                    result = tool_route_scanned(
                        args["phone"],
                        args["scanned_id"],
                        args["ts_local"],
                        args.get("stage"),
                        args.get("item_id"),
                    )
                elif name == "tool_decode_qr":
                    result = tool_decode_qr(args["media_id"])
                else:
                    result = {"ok": False, "error": f"unknown_tool:{name}"}

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result, ensure_ascii=False, default=_jsonable),
                    }
                )

            if sent_reply:
                break

            continue

        if msg.content and not sent_reply:
            wa_send_text(phone, msg.content)
            sent_reply = True
        break
