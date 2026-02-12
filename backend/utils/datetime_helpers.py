from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from backend.core.config import TZ_REGION

# ---------- TZ ----------
try:  
    import zoneinfo
    ZoneInfo = zoneinfo.ZoneInfo
except Exception:
    ZoneInfo = None


def now_local_iso() -> str:
    dt_utc = datetime.now(tz=timezone.utc)
    tz = ZoneInfo(TZ_REGION) if ZoneInfo else datetime.now().astimezone().tzinfo
    return dt_utc.astimezone(tz).isoformat(timespec="seconds")

def parse_duration_hms(td: timedelta) -> Tuple[str, int]:
    sec = max(0, int(td.total_seconds()))
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
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
