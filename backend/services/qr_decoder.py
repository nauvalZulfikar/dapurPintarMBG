import io
from typing import List
from PIL import Image
import numpy as np
import cv2

# ---------- QR decode ----------
try:
    from pyzbar.pyzbar import decode as zbar_decode
except Exception:
    zbar_decode = None

def decode_codes(img_bytes: bytes) -> List[str]:
    out: List[str] = []
    if zbar_decode:
        try:
            pil = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            for obj in zbar_decode(pil):
                if obj.data:
                    s = obj.data.decode("utf-8", errors="ignore").strip()
                    if s and s not in out:
                        out.append(s)
        except Exception:
            pass
    try:
        arr = np.frombuffer(img_bytes, np.uint8)
        cv_img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if cv_img is not None:
            data, _, _ = cv2.QRCodeDetector().detectAndDecode(cv_img)
            if data:
                s = data.strip()
                if s and s not in out:
                    out.append(s)
    except Exception:
        pass
    return out
