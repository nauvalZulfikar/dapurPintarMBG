from backend.services.whatsapp import wa_send_text, get_media_url, fetch_media
from backend.services.qr_decoder import decode_codes
from typing import Dict, Any
import re

def tool_send_text(phone: str, body: str) -> Dict[str, Any]:
    ok, resp = wa_send_text(phone, body)
    return {"ok": ok, "raw": resp}

def tool_decode_qr(media_id: str) -> Dict[str, Any]:
    try:
        url = get_media_url(media_id)
        img = fetch_media(url)
        texts = decode_codes(img)
        scanned = None
        for t in texts:
            mm = re.search(r"(?i)scanned-([A-Za-z0-9\-]+)", t)
            if mm:
                scanned = f"Scanned-{mm.group(1)}"
                break
        return {"ok": True, "raw_texts": texts, "scanned_text": scanned}
    except Exception as e:
        print(f"[IMG ERROR] {e}")
        return {"ok": False, "raw_texts": [], "scanned_text": None}
