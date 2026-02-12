from typing import Any, Dict, Optional
from backend.core.database import db_get_staff, db_last_event, db_insert_event, db_insert_tray_if_needed, db_recent_processed_item, db_insert_item
from backend.services.printing import db_create_print_job
from backend.utils.validators import is_item_id, is_tray_id, new_item_id
from backend.utils.datetime_helpers import compute_duration
from backend.core.database import engine, tray_items
from backend.services.printing import tspl_label, qr_link_for_item

def tool_route_scanned(
    phone: str,
    scanned_id: str,
    ts_local: str,
    stage: Optional[str] = None,
    item_id: Optional[str] = None,
) -> Dict[str, Any]:
    staff = db_get_staff(phone) or {}
    if not stage:
        stage = staff.get("division") or "unknown"

    if is_item_id(scanned_id):
        if stage == "unknown":
            stage = "processing"
        prev = db_last_event("item", scanned_id, division="receiving")
        prev_ts = prev["ts_local"] if prev else None
        dur_hms, dur_sec = compute_duration(ts_local, prev_ts)
        db_insert_event(
            ts_local,
            phone,
            stage,
            "item",
            scanned_id,
            f"Scanned-{scanned_id}",
            dur_hms,
            dur_sec,
            extra={},
        )
        return {"ok": True, "reply": f"{stage.capitalize()} with ID {scanned_id} has been added"}

    if is_tray_id(scanned_id):
        if stage == "unknown":
            stage = "packing"
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
                c.execute(
                    tray_items.insert().values(
                        tray_id=scanned_id, item_id=bound, bound_by_number=phone
                    )
                )
            db_insert_event(
                ts_local,
                phone,
                "packing",
                "tray",
                scanned_id,
                f"Scanned-{scanned_id}",
                dur_hms,
                dur_sec,
                extra={"bound_item": bound},
            )
            return {"ok": True, "reply": f"Packing with ID {scanned_id} has been added"}

        if stage == "delivery":
            prev = db_last_event("tray", scanned_id, division="packing")
            prev_ts = prev["ts_local"] if prev else None
            dur_hms, dur_sec = compute_duration(ts_local, prev_ts)
            db_insert_event(
                ts_local,
                phone,
                "delivery",
                "tray",
                scanned_id,
                f"Scanned-{scanned_id}",
                dur_hms,
                dur_sec,
                extra={},
            )
            return {"ok": True, "reply": f"Delivery with ID {scanned_id} has been added"}

        if stage == "school_receipt":
            prev = db_last_event("tray", scanned_id, division="delivery")
            prev_ts = prev["ts_local"] if prev else None
            dur_hms, dur_sec = compute_duration(ts_local, prev_ts)
            db_insert_event(
                ts_local,
                phone,
                "school_receipt",
                "tray",
                scanned_id,
                f"Scanned-{scanned_id}",
                dur_hms,
                dur_sec,
                extra={},
            )
            return {"ok": True, "reply": f"School_receipt with ID {scanned_id} has been added"}

        db_insert_event(
            ts_local,
            phone,
            stage,
            "tray",
            scanned_id,
            f"Scanned-{scanned_id}",
            "00:00:00",
            0,
            extra={},
        )
        return {"ok": True, "reply": f"{stage.capitalize()} with ID {scanned_id} has been added"}

    return {
        "ok": False,
        "reply": "Format ID tidak dikenal. Gunakan BHN-xxxxx (item) atau TRY-xxxxx (tray).",
    }

def tool_create_item(
    phone: str, name: str, weight_grams: int, unit: str, raw_text: str, ts_local: str
) -> Dict[str, Any]:
    item_id = new_item_id()
    db_insert_item(item_id, name, int(weight_grams), unit or "g")
    db_insert_event(
        ts_local,
        phone,
        "receiving",
        "item",
        item_id,
        raw_text,
        "00:00:00",
        0,
        extra={"name": name, "weight_grams": int(weight_grams)},
    )

    # Generate TSPL label and enqueue print job
    try:
        tspl = tspl_label(item_id, name, weight_grams)
        job_id = db_create_print_job(tspl)
        print(f"[PRINT QUEUE] Enqueued job_id={job_id} for item {item_id}")
    except Exception as e:
        print(f"[PRINT QUEUE ERROR] {e}")

    # Create WhatsApp link for item ID
    link = qr_link_for_item(item_id)
    return {
        "ok": True,
        "item_id": item_id,
        "link": link,
        "reply": f"Receive with ID {item_id} has been added\nScan QR: {link}",
    }
