from backend.core.config import TOKEN, GRAPH, PHONE_ID
from typing import Tuple
import requests

# ---------- WhatsApp ----------
def wa_url() -> str:
    return f"{GRAPH}/{PHONE_ID}/messages"

def wa_send_text(to: str, body: str) -> Tuple[bool, str]:
    headers = {"Authorization": f"Bearer {TOKEN}"}
    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }
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
