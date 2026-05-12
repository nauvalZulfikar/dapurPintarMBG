"""Executive dashboards (Phase 9) — 3 levels:
  - per-kitchen KPI    (any kitchen role)
  - multi-kitchen      (superadmin = yayasan owner across SPPGs in own org)
  - platform-wide      (platform_admin = lu/IT vendor, cross-org)

Plus BGN compliance bundle export.

Reuses aggregates from earlier phases — no new tables, no schema migration.
"""
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text

from backend.core.database import (
    engine,
    db_list_kitchens,
    db_list_organizations,
    db_audit_log,
)
from backend.utils.auth import get_current_user, get_current_kitchen
from backend.utils.permissions import (
    require_permission,
    is_platform_admin,
    is_org_superadmin,
)

router = APIRouter()

TARGET_COST_PER_PORSI = 15000


# ── Per-kitchen KPI snapshot ────────────────────────────────────────────────


def _kpi_for_kitchen(kid: int, target_date: str) -> dict:
    """Return today's KPI snapshot for a kitchen. Reuses queries from Phase 5/6/7."""
    with engine.connect() as c:
        # Items received today
        items_received = c.execute(text("""
            SELECT COUNT(*) FROM items
            WHERE kitchen_id = :k AND created_date_receiving = :d AND COALESCE(receiving, false) = true
        """), {"k": kid, "d": target_date}).scalar() or 0

        # Items processed today
        items_processed = c.execute(text("""
            SELECT COUNT(*) FROM items
            WHERE kitchen_id = :k AND created_date_processing = :d AND COALESCE(processing, false) = true
        """), {"k": kid, "d": target_date}).scalar() or 0

        # Trays packed/delivered today
        trays_packed = c.execute(text("""
            SELECT COUNT(*) FROM trays
            WHERE kitchen_id = :k AND created_date_packing = :d AND COALESCE(packing, false) = true
        """), {"k": kid, "d": target_date}).scalar() or 0
        trays_delivered = c.execute(text("""
            SELECT COUNT(*) FROM trays
            WHERE kitchen_id = :k AND created_date_delivery = :d AND COALESCE(delivery, false) = true
        """), {"k": kid, "d": target_date}).scalar() or 0

        # Confirmed by guru today
        confirmed = c.execute(text("""
            SELECT COALESCE(SUM(confirmed_count), 0) FROM delivery_confirmations
            WHERE kitchen_id = :k AND DATE(confirmed_at) = :d
        """), {"k": kid, "d": target_date}).scalar() or 0

        # Defects today
        defects_count = c.execute(text("""
            SELECT COUNT(*) FROM defect_items WHERE kitchen_id = :k AND created_date = :d
        """), {"k": kid, "d": target_date}).scalar() or 0

        # Today's expense + cost-per-porsi (today only — for full period use /finance/cost-per-porsi)
        expense_today = c.execute(text("""
            SELECT COALESCE(SUM(amount_idr), 0) FROM expenses
            WHERE kitchen_id = :k AND expense_date = :d
        """), {"k": kid, "d": target_date}).scalar() or 0

        # School targets (sum of student_count for active schools = today's potential demand)
        target_total = c.execute(text("""
            SELECT COALESCE(SUM(student_count), 0) FROM schools
            WHERE kitchen_id = :k AND is_active = true
        """), {"k": kid}).scalar() or 0

    items_received = int(items_received)
    items_processed = int(items_processed)
    trays_packed = int(trays_packed)
    trays_delivered = int(trays_delivered)
    confirmed = int(confirmed)
    defects_count = int(defects_count)
    expense_today = int(expense_today)
    target_total = int(target_total)

    defect_rate = round((defects_count / items_received) * 100, 2) if items_received > 0 else 0.0
    cost_per_porsi_today = int(expense_today / confirmed) if confirmed > 0 else 0

    return {
        "kitchen_id": kid,
        "date": target_date,
        "target_porsi": target_total,
        "items_received": items_received,
        "items_processed": items_processed,
        "trays_packed": trays_packed,
        "trays_delivered": trays_delivered,
        "porsi_confirmed": confirmed,
        "defects_count": defects_count,
        "defect_rate_pct": defect_rate,
        "expense_today_idr": expense_today,
        "cost_per_porsi_today_idr": cost_per_porsi_today,
        "cost_per_porsi_target_idr": TARGET_COST_PER_PORSI,
        "cost_over_target": cost_per_porsi_today > TARGET_COST_PER_PORSI if cost_per_porsi_today else False,
    }


def _compliance_score(kid: int, days: int = 30) -> dict:
    """Composite 5-factor compliance score (0-100).
       - inspections_completed_pct
       - menus_approved_on_time_pct
       - distribution_confirmed_pct
       - lra_submitted_on_time_pct
       - daily_checklists_done_pct
    """
    today = date.today()
    cutoff = (today - timedelta(days=days)).isoformat()
    today_str = today.isoformat()

    with engine.connect() as c:
        # 1. Inspections: % accepted/partial vs total in range
        insp_total = c.execute(text("""
            SELECT COUNT(*) FROM receiving_inspections
            WHERE kitchen_id = :k AND created_at >= :a
        """), {"k": kid, "a": cutoff}).scalar() or 0
        insp_done = c.execute(text("""
            SELECT COUNT(*) FROM receiving_inspections
            WHERE kitchen_id = :k AND created_at >= :a AND status IN ('accepted', 'partial')
        """), {"k": kid, "a": cutoff}).scalar() or 0
        inspection_pct = round((insp_done / insp_total) * 100, 1) if insp_total > 0 else 100.0

        # 2. Menu approved on-time
        menu_total = c.execute(text("""
            SELECT COUNT(*) FROM saved_menus
            WHERE kitchen_id = :k AND COALESCE(target_date, created_at::date) >= :a
        """), {"k": kid, "a": cutoff}).scalar() or 0
        menu_approved = c.execute(text("""
            SELECT COUNT(*) FROM saved_menus
            WHERE kitchen_id = :k AND COALESCE(target_date, created_at::date) >= :a
              AND status IN ('approved', 'locked')
        """), {"k": kid, "a": cutoff}).scalar() or 0
        menu_pct = round((menu_approved / menu_total) * 100, 1) if menu_total > 0 else 100.0

        # 3. Distribution confirmed
        dispatched_today = c.execute(text("""
            SELECT COUNT(*) FROM trays
            WHERE kitchen_id = :k AND created_date_delivery >= :a AND COALESCE(delivery, false) = true
        """), {"k": kid, "a": cutoff}).scalar() or 0
        confirmed_count = c.execute(text("""
            SELECT COUNT(*) FROM delivery_confirmations
            WHERE kitchen_id = :k AND DATE(confirmed_at) >= :a
        """), {"k": kid, "a": cutoff}).scalar() or 0
        # Loose proxy: confirmations should at least equal dispatched scans/10 (because 1 scan = 10 ompreng).
        dist_pct = min(100.0, round((confirmed_count / dispatched_today) * 100 if dispatched_today > 0 else 100, 1)) if dispatched_today > 0 else 100.0

        # 4. LRA submitted (each biweekly period since cutoff should have submitted status)
        lra_total = c.execute(text("""
            SELECT COUNT(*) FROM lra_periods
            WHERE kitchen_id = :k AND period_end >= :a
        """), {"k": kid, "a": cutoff}).scalar() or 0
        lra_submitted = c.execute(text("""
            SELECT COUNT(*) FROM lra_periods
            WHERE kitchen_id = :k AND period_end >= :a AND status = 'submitted'
        """), {"k": kid, "a": cutoff}).scalar() or 0
        lra_pct = round((lra_submitted / lra_total) * 100, 1) if lra_total > 0 else 100.0

        # 5. Daily checklists done
        checklist_submitted = c.execute(text("""
            SELECT COUNT(*) FROM daily_checklists
            WHERE kitchen_id = :k AND checklist_date >= :a AND status = 'submitted'
        """), {"k": kid, "a": cutoff}).scalar() or 0
        checklist_pct = round((checklist_submitted / days) * 100, 1)

    factors = {
        "inspections_completed_pct": inspection_pct,
        "menus_approved_pct":        menu_pct,
        "distribution_confirmed_pct": dist_pct,
        "lra_submitted_pct":         lra_pct,
        "daily_checklists_done_pct": min(100.0, checklist_pct),
    }
    composite = round(sum(factors.values()) / len(factors), 1)
    return {
        "days":      days,
        "factors":   factors,
        "composite": composite,
        "grade":     "A" if composite >= 90 else "B" if composite >= 75 else "C" if composite >= 60 else "D",
    }


@router.get("/executive/kpi")
async def kpi_today(
    target_date: Optional[str] = None,
    kitchen: dict = Depends(require_permission("executive.kpi_view")),
):
    d = target_date or str(date.today())
    return _kpi_for_kitchen(kitchen["id"], d)


@router.get("/executive/compliance-score")
async def compliance_score(
    days: int = 30,
    kitchen: dict = Depends(require_permission("executive.kpi_view")),
):
    if days < 7 or days > 365:
        raise HTTPException(400, "days must be between 7 and 365")
    return _compliance_score(kitchen["id"], days=days)


@router.get("/executive/trend")
async def kpi_trend(
    metric: str = "porsi_confirmed",
    days: int = 30,
    kitchen: dict = Depends(require_permission("executive.kpi_view")),
):
    """Daily series for one metric across `days`. Skips heavy KPIs — uses
    direct SQL per metric for speed.
    """
    if days < 7 or days > 90:
        raise HTTPException(400, "days must be between 7 and 90")
    today = date.today()
    series = []
    with engine.connect() as c:
        for i in range(days):
            d = (today - timedelta(days=days - 1 - i)).isoformat()
            if metric == "porsi_confirmed":
                v = c.execute(text(
                    "SELECT COALESCE(SUM(confirmed_count), 0) FROM delivery_confirmations "
                    "WHERE kitchen_id = :k AND DATE(confirmed_at) = :d"
                ), {"k": kitchen["id"], "d": d}).scalar() or 0
            elif metric == "expense":
                v = c.execute(text(
                    "SELECT COALESCE(SUM(amount_idr), 0) FROM expenses "
                    "WHERE kitchen_id = :k AND expense_date = :d"
                ), {"k": kitchen["id"], "d": d}).scalar() or 0
            elif metric == "defects":
                v = c.execute(text(
                    "SELECT COUNT(*) FROM defect_items WHERE kitchen_id = :k AND created_date = :d"
                ), {"k": kitchen["id"], "d": d}).scalar() or 0
            elif metric == "items_received":
                v = c.execute(text(
                    "SELECT COUNT(*) FROM items WHERE kitchen_id = :k AND created_date_receiving = :d"
                ), {"k": kitchen["id"], "d": d}).scalar() or 0
            else:
                raise HTTPException(400, f"Unknown metric: {metric}")
            series.append({"date": d, "value": int(v)})
    return {"metric": metric, "days": days, "series": series}


# ── Multi-kitchen view (superadmin / yayasan owner) ────────────────────────


@router.get("/executive/multi-kitchen")
async def multi_kitchen(
    target_date: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    """Aggregate per-kitchen KPI within caller's org. platform_admin sees all,
    superadmin sees own org only.
    """
    if not (is_platform_admin(user) or is_org_superadmin(user)):
        raise HTTPException(403, "Multi-kitchen view requires superadmin or platform_admin role.")
    d = target_date or str(date.today())
    org_filter = None if is_platform_admin(user) else user.get("org_id")
    kitchens = db_list_kitchens(active_only=True, org_id=org_filter)

    results = []
    for k in kitchens:
        kpi = _kpi_for_kitchen(k["id"], d)
        comp = _compliance_score(k["id"], days=30)
        results.append({
            "kitchen_id":    k["id"],
            "kitchen_name":  k["name"],
            "org_id":        k.get("org_id"),
            "kpi":           kpi,
            "compliance":    comp,
        })

    # Build rankings.
    by_compliance = sorted(results, key=lambda r: -r["compliance"]["composite"])
    by_cost = sorted(
        [r for r in results if r["kpi"]["cost_per_porsi_today_idr"] > 0],
        key=lambda r: r["kpi"]["cost_per_porsi_today_idr"],
    )
    by_defect = sorted(results, key=lambda r: -r["kpi"]["defect_rate_pct"])

    return {
        "date":           d,
        "kitchens_count": len(results),
        "kitchens":       results,
        "rankings": {
            "best_compliance":  [r["kitchen_name"] for r in by_compliance[:3]],
            "lowest_cost":      [r["kitchen_name"] for r in by_cost[:3]],
            "highest_defect":   [r["kitchen_name"] for r in by_defect[:3] if r["kpi"]["defect_rate_pct"] > 0],
        },
    }


# ── Platform-wide view (platform_admin = lu) ───────────────────────────────


@router.get("/executive/platform")
async def platform_overview(user: dict = Depends(get_current_user)):
    if not is_platform_admin(user):
        raise HTTPException(403, "Platform overview is platform_admin only.")
    today_str = str(date.today())

    with engine.connect() as c:
        org_count = c.execute(text("SELECT COUNT(*) FROM organizations WHERE active = true")).scalar() or 0
        kitchen_count = c.execute(text("SELECT COUNT(*) FROM kitchens WHERE active = true")).scalar() or 0
        user_count = c.execute(text("SELECT COUNT(*) FROM users")).scalar() or 0
        porsi_today = c.execute(text("""
            SELECT COALESCE(SUM(confirmed_count), 0) FROM delivery_confirmations
            WHERE DATE(confirmed_at) = :d
        """), {"d": today_str}).scalar() or 0
        items_today = c.execute(text("""
            SELECT COUNT(*) FROM items WHERE created_date_receiving = :d
        """), {"d": today_str}).scalar() or 0

        # Per-org snapshot
        orgs = db_list_organizations(active_only=True)
        per_org = []
        for o in orgs:
            kw = c.execute(text("""
                SELECT COUNT(*) FROM kitchens WHERE org_id = :o AND active = true
            """), {"o": o["id"]}).scalar() or 0
            porsi_o = c.execute(text("""
                SELECT COALESCE(SUM(d.confirmed_count), 0)
                FROM delivery_confirmations d
                JOIN kitchens k ON k.id = d.kitchen_id
                WHERE k.org_id = :o AND DATE(d.confirmed_at) = :d
            """), {"o": o["id"], "d": today_str}).scalar() or 0
            lra_late = c.execute(text("""
                SELECT COUNT(*) FROM lra_periods l
                JOIN kitchens k ON k.id = l.kitchen_id
                WHERE k.org_id = :o AND l.status != 'submitted' AND l.period_end < CURRENT_DATE - INTERVAL '7 days'
            """), {"o": o["id"]}).scalar() or 0
            per_org.append({
                "org_id":          o["id"],
                "org_name":        o["name"],
                "kitchens":        int(kw),
                "porsi_today":     int(porsi_o),
                "lra_late_count":  int(lra_late),
                "churn_risk":      bool(lra_late >= 2),
            })

    return {
        "date":          today_str,
        "totals": {
            "organizations":     int(org_count),
            "kitchens":          int(kitchen_count),
            "users":             int(user_count),
            "porsi_nasional":    int(porsi_today),
            "items_received":    int(items_today),
        },
        "per_org": per_org,
    }


# ── BGN Compliance Bundle ──────────────────────────────────────────────────


@router.get("/compliance/bundle")
async def compliance_bundle(
    from_date: str,
    to_date: str,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("compliance.bundle_export")),
):
    """Snapshot bundle for BGN audit: LRA + samples + checklists + variance +
    attendance, compiled into one JSON payload (frontend can ZIP / PDF later).
    """
    try:
        date.fromisoformat(from_date)
        date.fromisoformat(to_date)
    except ValueError:
        raise HTTPException(400, "Invalid date format")
    if from_date > to_date:
        raise HTTPException(400, "from_date must be <= to_date")

    kid = kitchen["id"]
    with engine.connect() as c:
        lra = [dict(r._mapping) for r in c.execute(text("""
            SELECT id, period_start, period_end, status, total_revenue_idr, total_expense_idr,
                   total_porsi, cost_per_porsi, generated_at, submitted_at
            FROM lra_periods
            WHERE kitchen_id = :k AND period_start >= :a AND period_end <= :b
            ORDER BY period_start
        """), {"k": kid, "a": from_date, "b": to_date}).fetchall()]

        samples = [dict(r._mapping) for r in c.execute(text("""
            SELECT id, batch_id, menu_name, location, collected_at, expire_at, status
            FROM food_samples
            WHERE kitchen_id = :k AND DATE(collected_at) BETWEEN :a AND :b
            ORDER BY collected_at
        """), {"k": kid, "a": from_date, "b": to_date}).fetchall()]

        checklists = c.execute(text("""
            SELECT COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE status = 'submitted') AS submitted
            FROM daily_checklists
            WHERE kitchen_id = :k AND checklist_date BETWEEN :a AND :b
        """), {"k": kid, "a": from_date, "b": to_date}).first()

        defects_count = c.execute(text("""
            SELECT COUNT(*) FROM defect_items
            WHERE kitchen_id = :k AND created_date BETWEEN :a AND :b
        """), {"k": kid, "a": from_date, "b": to_date}).scalar() or 0

        items_received = c.execute(text("""
            SELECT COUNT(*) FROM items
            WHERE kitchen_id = :k AND created_date_receiving BETWEEN :a AND :b
        """), {"k": kid, "a": from_date, "b": to_date}).scalar() or 0

        porsi_total = c.execute(text("""
            SELECT COALESCE(SUM(confirmed_count), 0) FROM delivery_confirmations
            WHERE kitchen_id = :k AND DATE(confirmed_at) BETWEEN :a AND :b
        """), {"k": kid, "a": from_date, "b": to_date}).scalar() or 0

    bundle = {
        "kitchen_id":   kid,
        "kitchen_name": kitchen.get("name"),
        "from_date":    from_date,
        "to_date":      to_date,
        "generated_at": datetime.now().isoformat(),
        "lra_periods": [
            {**r,
             "period_start": str(r["period_start"]) if r["period_start"] else None,
             "period_end":   str(r["period_end"]) if r["period_end"] else None,
             "generated_at": r["generated_at"].isoformat() if r["generated_at"] else None,
             "submitted_at": r["submitted_at"].isoformat() if r["submitted_at"] else None}
            for r in lra
        ],
        "food_samples_count": len(samples),
        "food_samples": [
            {**s,
             "collected_at": s["collected_at"].isoformat() if s["collected_at"] else None,
             "expire_at":    s["expire_at"].isoformat() if s["expire_at"] else None}
            for s in samples
        ],
        "daily_checklists": {
            "total":     int(checklists.total or 0),
            "submitted": int(checklists.submitted or 0),
        },
        "variance": {
            "items_received":  int(items_received),
            "defects_count":   int(defects_count),
            "defect_rate_pct": round((int(defects_count) / int(items_received)) * 100, 2) if items_received > 0 else 0.0,
        },
        "porsi_total": int(porsi_total),
    }
    db_audit_log(
        action="compliance.bundle_export",
        user_id=user.get("id"),
        kitchen_id=kid,
        org_id=user.get("org_id"),
        target_type="compliance_bundle",
        target_id=f"{from_date}_to_{to_date}",
        after_value={"lra": len(lra), "samples": len(samples), "porsi": int(porsi_total)},
    )
    return bundle
