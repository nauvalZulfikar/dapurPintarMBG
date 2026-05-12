"""ASLAP daily ops (Phase 7).

Cerita pagi Mas Toni (ASLAP):
  Jam 06:00 buka tablet → daily checklist auto-load (kebersihan, suhu kompor,
  cuci tangan, sampah, water test). Submit dengan foto. Per batch produksi
  (Phase 4) submit observasi. Logbook komunikasi sekolah. Akhir minggu →
  /aslap/reports/generate compile snapshot to PDF-able JSON.

Permissions:
  checklist.daily / .view              — aslap, head_sppg
  water_quality.log / .view            — aslap, head_sppg
  production_observation.create / view — aslap, head_sppg
  school_comm_log.create / view        — aslap, head_sppg
  aslap_report.generate / view         — aslap, head_sppg
  aslap_report.signoff                 — head_sppg only (final)
"""
import json as _json
from datetime import date, datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, text

from backend.core.database import (
    engine,
    remote_daily_checklists,
    remote_water_quality_logs,
    remote_production_observations,
    remote_school_comm_logs,
    remote_aslap_weekly_reports,
    db_audit_log,
)
from backend.utils.auth import get_current_user
from backend.utils.permissions import require_permission

router = APIRouter()

DEFAULT_CHECKLIST_ITEMS = [
    {"key": "dapur_bersih",     "label": "Dapur dibersihkan?",                     "type": "bool", "required": True},
    {"key": "suhu_kompor",      "label": "Suhu kompor 180-200°C?",                  "type": "bool", "required": True},
    {"key": "cuci_tangan",      "label": "Tim cuci tangan sebelum masak?",          "type": "bool", "required": True},
    {"key": "sampah_organik",   "label": "Sampah organik dipisah?",                 "type": "bool", "required": False},
    {"key": "kulkas_suhu",      "label": "Suhu kulkas (≤4°C)?",                     "type": "number", "required": False},
    {"key": "alat_masak",       "label": "Alat masak steril?",                      "type": "bool", "required": True},
    {"key": "apd_lengkap",      "label": "Tim pakai APD lengkap (celemek+masker+sarung tangan)?", "type": "bool", "required": True},
]

WATER_TDS_MAX = 500
WATER_PH_MIN = 6.5
WATER_PH_MAX = 8.5


# ── Daily Checklist ─────────────────────────────────────────────────────────


class ChecklistSubmitBody(BaseModel):
    checklist_date: Optional[str] = None
    items:          list[dict]                # array of {key, value, photo, ok, notes}
    notes:          Optional[str] = None
    submit:         bool = True               # if false → save as draft only


@router.get("/aslap/checklists/today")
async def get_today_checklist(
    target_date: Optional[str] = None,
    kitchen: dict = Depends(require_permission("checklist.view")),
):
    """Return today's checklist (existing draft or empty template)."""
    d = target_date or str(date.today())
    with engine.connect() as c:
        row = c.execute(
            select(remote_daily_checklists).where(
                (remote_daily_checklists.c.kitchen_id == kitchen["id"]) &
                (remote_daily_checklists.c.checklist_date == d)
            ).order_by(remote_daily_checklists.c.id.desc()).limit(1)
        ).first()

    if row:
        try:
            items = _json.loads(row.items_json)
        except Exception:
            items = []
        return {
            "id": row.id, "checklist_date": str(row.checklist_date),
            "status": row.status, "notes": row.notes,
            "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
            "items": items,
        }
    # No row yet — return template scaffold.
    return {
        "id": None, "checklist_date": d, "status": "draft",
        "items": [{**it, "value": None, "photo": None, "ok": None} for it in DEFAULT_CHECKLIST_ITEMS],
    }


@router.post("/aslap/checklists/submit")
async def submit_checklist(
    body: ChecklistSubmitBody,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("checklist.daily")),
):
    d = body.checklist_date or str(date.today())
    items_json = _json.dumps(body.items, ensure_ascii=False)
    new_status = "submitted" if body.submit else "draft"

    with engine.begin() as c:
        existing = c.execute(
            select(remote_daily_checklists.c.id).where(
                (remote_daily_checklists.c.kitchen_id == kitchen["id"]) &
                (remote_daily_checklists.c.checklist_date == d)
            )
        ).first()
        if existing:
            c.execute(
                remote_daily_checklists.update()
                .where(remote_daily_checklists.c.id == existing.id)
                .values(
                    items_json=items_json,
                    status=new_status,
                    notes=body.notes,
                    submitted_by=user.get("id") if body.submit else None,
                    submitted_at=datetime.now() if body.submit else None,
                )
            )
            new_id = existing.id
        else:
            res = c.execute(
                remote_daily_checklists.insert().values(
                    kitchen_id=kitchen["id"],
                    checklist_date=d,
                    items_json=items_json,
                    status=new_status,
                    notes=body.notes,
                    submitted_by=user.get("id") if body.submit else None,
                    submitted_at=datetime.now() if body.submit else None,
                )
                .returning(remote_daily_checklists.c.id)
            )
            new_id = res.scalar()

    db_audit_log(
        action="checklist.submit" if body.submit else "checklist.save_draft",
        user_id=user.get("id"),
        kitchen_id=kitchen["id"],
        org_id=user.get("org_id"),
        target_type="checklist",
        target_id=str(new_id),
        after_value={"date": d, "status": new_status, "item_count": len(body.items)},
    )
    return await get_today_checklist(target_date=d, kitchen=kitchen)


@router.get("/aslap/checklists")
async def list_checklists(
    from_date: Optional[str] = None,
    to_date:   Optional[str] = None,
    kitchen: dict = Depends(require_permission("checklist.view")),
):
    """Historical checklists in date range."""
    f = from_date or str(date.today() - timedelta(days=7))
    t = to_date or str(date.today())
    with engine.connect() as c:
        rows = c.execute(
            select(
                remote_daily_checklists.c.id,
                remote_daily_checklists.c.checklist_date,
                remote_daily_checklists.c.status,
                remote_daily_checklists.c.submitted_at,
                remote_daily_checklists.c.notes,
            ).where(
                (remote_daily_checklists.c.kitchen_id == kitchen["id"]) &
                (remote_daily_checklists.c.checklist_date >= f) &
                (remote_daily_checklists.c.checklist_date <= t)
            ).order_by(remote_daily_checklists.c.checklist_date.desc())
        ).all()
    return {
        "from_date": f, "to_date": t,
        "checklists": [
            {
                "id": r.id, "checklist_date": str(r.checklist_date),
                "status": r.status, "notes": r.notes,
                "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
            }
            for r in rows
        ],
    }


# ── Water Quality ───────────────────────────────────────────────────────────


class WaterLogBody(BaseModel):
    log_date:   Optional[str] = None
    tds_ppm:    Optional[int] = None
    ph:         Optional[str] = None
    bau:        Optional[str] = None
    warna:      Optional[str] = None
    photo_path: Optional[str] = None
    notes:      Optional[str] = None


def _check_water_alerts(b: WaterLogBody) -> list[str]:
    """Threshold checks: BGN / Permenkes 32/2017."""
    alerts: list[str] = []
    if b.tds_ppm is not None and b.tds_ppm > WATER_TDS_MAX:
        alerts.append(f"TDS {b.tds_ppm} ppm > batas {WATER_TDS_MAX} ppm")
    if b.ph:
        try:
            ph_f = float(b.ph)
            if ph_f < WATER_PH_MIN:
                alerts.append(f"pH {ph_f} < min {WATER_PH_MIN}")
            elif ph_f > WATER_PH_MAX:
                alerts.append(f"pH {ph_f} > max {WATER_PH_MAX}")
        except (TypeError, ValueError):
            pass
    if b.bau and b.bau.lower() not in ("normal", "tidak ada", ""):
        alerts.append(f"Bau: {b.bau}")
    if b.warna and b.warna.lower() not in ("jernih", "bening", ""):
        alerts.append(f"Warna: {b.warna}")
    return alerts


@router.post("/aslap/water-quality", status_code=201)
async def submit_water_quality(
    body: WaterLogBody,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("water_quality.log")),
):
    d = body.log_date or str(date.today())
    alerts = _check_water_alerts(body)
    flags_json = _json.dumps(alerts, ensure_ascii=False) if alerts else None

    with engine.begin() as c:
        res = c.execute(
            remote_water_quality_logs.insert().values(
                kitchen_id=kitchen["id"],
                log_date=d,
                tds_ppm=body.tds_ppm,
                ph=body.ph,
                bau=body.bau,
                warna=body.warna,
                photo_path=body.photo_path,
                tester_id=user.get("id"),
                alert_flags=flags_json,
                notes=body.notes,
            ).returning(remote_water_quality_logs.c.id)
        )
        new_id = res.scalar()

    db_audit_log(
        action="water_quality.log",
        user_id=user.get("id"),
        kitchen_id=kitchen["id"],
        org_id=user.get("org_id"),
        target_type="water_quality",
        target_id=str(new_id),
        after_value={"date": d, "tds": body.tds_ppm, "ph": body.ph, "alerts": alerts},
    )
    return {"id": new_id, "alerts": alerts, "alert_count": len(alerts)}


@router.get("/aslap/water-quality")
async def list_water_quality(
    from_date: Optional[str] = None,
    to_date:   Optional[str] = None,
    kitchen: dict = Depends(require_permission("water_quality.view")),
):
    f = from_date or str(date.today() - timedelta(days=7))
    t = to_date or str(date.today())
    with engine.connect() as c:
        rows = c.execute(
            select(remote_water_quality_logs).where(
                (remote_water_quality_logs.c.kitchen_id == kitchen["id"]) &
                (remote_water_quality_logs.c.log_date >= f) &
                (remote_water_quality_logs.c.log_date <= t)
            ).order_by(remote_water_quality_logs.c.log_date.desc(), remote_water_quality_logs.c.id.desc())
        ).all()

    out = []
    for r in rows:
        try:
            alerts = _json.loads(r.alert_flags) if r.alert_flags else []
        except Exception:
            alerts = []
        out.append({
            "id": r.id, "log_date": str(r.log_date),
            "tds_ppm": r.tds_ppm, "ph": r.ph, "bau": r.bau, "warna": r.warna,
            "photo_path": r.photo_path, "alerts": alerts,
            "alert_count": len(alerts), "notes": r.notes,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return {"from_date": f, "to_date": t, "logs": out}


# ── Production Observations ─────────────────────────────────────────────────


class ObservationBody(BaseModel):
    batch_id:        Optional[int] = None
    suhu_masak:      Optional[int] = None
    waktu_menit:     Optional[int] = None
    kebersihan_ok:   bool = True
    photo_path:      Optional[str] = None
    notes:           Optional[str] = None


@router.post("/aslap/observations", status_code=201)
async def create_observation(
    body: ObservationBody,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("production_observation.create")),
):
    with engine.begin() as c:
        res = c.execute(
            remote_production_observations.insert().values(
                kitchen_id=kitchen["id"],
                batch_id=body.batch_id,
                observer_id=user.get("id"),
                **body.model_dump(exclude={"batch_id"}),
            ).returning(remote_production_observations.c.id)
        )
        new_id = res.scalar()

    db_audit_log(
        action="observation.create",
        user_id=user.get("id"),
        kitchen_id=kitchen["id"],
        org_id=user.get("org_id"),
        target_type="observation",
        target_id=str(new_id),
        after_value={"batch_id": body.batch_id, "suhu": body.suhu_masak, "waktu": body.waktu_menit},
    )
    return {"id": new_id}


@router.get("/aslap/observations")
async def list_observations(
    from_date: Optional[str] = None,
    to_date:   Optional[str] = None,
    batch_id:  Optional[int] = None,
    kitchen: dict = Depends(require_permission("production_observation.view")),
):
    with engine.connect() as c:
        q = select(remote_production_observations).where(
            remote_production_observations.c.kitchen_id == kitchen["id"]
        )
        if batch_id:
            q = q.where(remote_production_observations.c.batch_id == batch_id)
        if from_date:
            q = q.where(remote_production_observations.c.observed_at >= from_date)
        if to_date:
            q = q.where(remote_production_observations.c.observed_at <= to_date + " 23:59:59")
        rows = c.execute(q.order_by(remote_production_observations.c.observed_at.desc())).all()
    return {
        "observations": [
            {
                "id": r.id, "batch_id": r.batch_id,
                "suhu_masak": r.suhu_masak, "waktu_menit": r.waktu_menit,
                "kebersihan_ok": r.kebersihan_ok, "photo_path": r.photo_path,
                "notes": r.notes,
                "observed_at": r.observed_at.isoformat() if r.observed_at else None,
            }
            for r in rows
        ],
    }


# ── School Communication Log ───────────────────────────────────────────────


VALID_CHANNELS = ("call", "wa", "email", "visit", "sms")


class CommLogBody(BaseModel):
    school_id:   Optional[int] = None
    school_name: Optional[str] = None
    channel:     str
    topic:       str
    response:    Optional[str] = None
    follow_up:   bool = False


@router.post("/aslap/comm-logs", status_code=201)
async def create_comm_log(
    body: CommLogBody,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("school_comm_log.create")),
):
    if body.channel not in VALID_CHANNELS:
        raise HTTPException(400, f"channel invalid. Valid: {', '.join(VALID_CHANNELS)}")
    with engine.begin() as c:
        res = c.execute(
            remote_school_comm_logs.insert().values(
                kitchen_id=kitchen["id"],
                created_by=user.get("id"),
                **body.model_dump(),
            ).returning(remote_school_comm_logs.c.id)
        )
        new_id = res.scalar()

    db_audit_log(
        action="comm_log.create",
        user_id=user.get("id"),
        kitchen_id=kitchen["id"],
        org_id=user.get("org_id"),
        target_type="comm_log",
        target_id=str(new_id),
        after_value={"school": body.school_name, "channel": body.channel, "topic": body.topic},
    )
    return {"id": new_id}


@router.get("/aslap/comm-logs")
async def list_comm_logs(
    from_date: Optional[str] = None,
    to_date:   Optional[str] = None,
    kitchen: dict = Depends(require_permission("school_comm_log.view")),
):
    f = from_date or str(date.today() - timedelta(days=14))
    t = to_date or str(date.today())
    with engine.connect() as c:
        rows = c.execute(
            select(remote_school_comm_logs).where(
                (remote_school_comm_logs.c.kitchen_id == kitchen["id"]) &
                (remote_school_comm_logs.c.created_at >= f) &
                (remote_school_comm_logs.c.created_at <= t + " 23:59:59")
            ).order_by(remote_school_comm_logs.c.created_at.desc())
        ).all()
    return {
        "logs": [
            {
                "id": r.id, "school_id": r.school_id, "school_name": r.school_name,
                "channel": r.channel, "topic": r.topic, "response": r.response,
                "follow_up": r.follow_up,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


# ── Weekly Report ──────────────────────────────────────────────────────────


class WeeklyReportBody(BaseModel):
    week_start: str   # YYYY-MM-DD (Senin)
    week_end:   str


@router.post("/aslap/reports/generate", status_code=201)
async def generate_weekly_report(
    body: WeeklyReportBody,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("aslap_report.generate")),
):
    """Aggregate semua aktivitas ASLAP minggu ini → snapshot JSON."""
    try:
        date.fromisoformat(body.week_start)
        date.fromisoformat(body.week_end)
    except ValueError:
        raise HTTPException(400, "Invalid date format")
    if body.week_start > body.week_end:
        raise HTTPException(400, "week_start must be ≤ week_end")

    kid = kitchen["id"]
    with engine.connect() as c:
        chk = c.execute(text("""
            SELECT COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE status='submitted') AS submitted
            FROM daily_checklists
            WHERE kitchen_id = :k AND checklist_date BETWEEN :a AND :b
        """), {"k": kid, "a": body.week_start, "b": body.week_end}).first()

        wq = c.execute(text("""
            SELECT COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE alert_flags IS NOT NULL AND alert_flags != '[]') AS with_alerts
            FROM water_quality_logs
            WHERE kitchen_id = :k AND log_date BETWEEN :a AND :b
        """), {"k": kid, "a": body.week_start, "b": body.week_end}).first()

        obs = c.execute(text("""
            SELECT COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE kebersihan_ok = false) AS unclean,
                   AVG(suhu_masak) AS avg_suhu,
                   AVG(waktu_menit) AS avg_waktu
            FROM production_observations
            WHERE kitchen_id = :k AND observed_at BETWEEN :a AND :b
        """), {"k": kid, "a": body.week_start, "b": body.week_end + " 23:59:59"}).first()

        comm = c.execute(text("""
            SELECT COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE follow_up = true) AS need_followup
            FROM school_comm_logs
            WHERE kitchen_id = :k AND created_at BETWEEN :a AND :b
        """), {"k": kid, "a": body.week_start, "b": body.week_end + " 23:59:59"}).first()

    summary = {
        "week_start": body.week_start,
        "week_end":   body.week_end,
        "checklists": {
            "total":     int(chk.total or 0),
            "submitted": int(chk.submitted or 0),
            "missed":    7 - int(chk.submitted or 0),
        },
        "water_quality": {
            "total":       int(wq.total or 0),
            "with_alerts": int(wq.with_alerts or 0),
        },
        "production_observations": {
            "total":     int(obs.total or 0),
            "unclean":   int(obs.unclean or 0),
            "avg_suhu":  round(float(obs.avg_suhu or 0), 1),
            "avg_waktu": round(float(obs.avg_waktu or 0), 1),
        },
        "school_communications": {
            "total":         int(comm.total or 0),
            "need_followup": int(comm.need_followup or 0),
        },
    }
    summary_json = _json.dumps(summary, ensure_ascii=False)

    with engine.begin() as c:
        res = c.execute(
            remote_aslap_weekly_reports.insert().values(
                kitchen_id=kid,
                week_start=body.week_start,
                week_end=body.week_end,
                summary_json=summary_json,
                status="draft",
                generated_by=user.get("id"),
            ).returning(remote_aslap_weekly_reports.c.id)
        )
        new_id = res.scalar()

    db_audit_log(
        action="aslap.report_generate",
        user_id=user.get("id"),
        kitchen_id=kid,
        org_id=user.get("org_id"),
        target_type="aslap_report",
        target_id=str(new_id),
        after_value=summary,
    )
    return {"id": new_id, "summary": summary}


@router.get("/aslap/reports")
async def list_reports(kitchen: dict = Depends(require_permission("aslap_report.view"))):
    with engine.connect() as c:
        rows = c.execute(
            select(remote_aslap_weekly_reports).where(
                remote_aslap_weekly_reports.c.kitchen_id == kitchen["id"]
            ).order_by(remote_aslap_weekly_reports.c.week_start.desc())
        ).all()
    out = []
    for r in rows:
        try:
            summary = _json.loads(r.summary_json) if r.summary_json else {}
        except Exception:
            summary = {}
        out.append({
            "id": r.id, "week_start": str(r.week_start), "week_end": str(r.week_end),
            "status": r.status, "summary": summary,
            "generated_at": r.generated_at.isoformat() if r.generated_at else None,
            "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
        })
    return {"reports": out}


@router.post("/aslap/reports/{report_id}/submit")
async def submit_report(
    report_id: int,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("aslap_report.signoff")),
):
    """Head SPPG signs off → forwards to Yayasan / BGN."""
    with engine.begin() as c:
        res = c.execute(
            remote_aslap_weekly_reports.update()
            .where(
                (remote_aslap_weekly_reports.c.id == report_id) &
                (remote_aslap_weekly_reports.c.kitchen_id == kitchen["id"])
            )
            .values(status="submitted", submitted_at=datetime.now())
        )
        if res.rowcount == 0:
            raise HTTPException(404, "Report tidak ditemukan.")
    db_audit_log(
        action="aslap.report_submit",
        user_id=user.get("id"),
        kitchen_id=kitchen["id"],
        org_id=user.get("org_id"),
        target_type="aslap_report",
        target_id=str(report_id),
    )
    return {"ok": True}
