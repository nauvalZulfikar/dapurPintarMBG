"""Akuntan finance module (Phase 6).

4 sub-modules:

  6A — Price Trend Dashboard
       reuses food_prices_history (existing daily scrape) + food_prices manual.
  6B — Spike Alert + Forecast
       wraps Phase 2B /menu/forecast and overlays current prices to detect
       week-over-week price changes.
  6C — PO Generator from Forecast
       builds a draft PO from forecast bahan + supplier preference.
  6D — Expense Tracker + LRA Biweekly
       8-category expense + volunteer honor + cost-per-porsi + LRA snapshot.

Permissions:
  finance.view             — head_sppg, accountant
  finance.price_trends     — head_sppg, accountant, nutritionist
  expense.view / .create   — head_sppg, accountant
  expense.edit             — head_sppg, accountant
  volunteer.manage         — head_sppg, accountant
  lra.view / .generate     — head_sppg, accountant
  lra.signoff              — head_sppg only (final approval before submit)
"""
from datetime import date, datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func, text

from backend.core.database import (
    engine,
    remote_food_prices,
    remote_food_prices_history,
    remote_expenses,
    remote_volunteer_payments,
    remote_lra_periods,
    remote_purchase_orders,
    remote_po_lines,
    remote_suppliers,
    remote_delivery_confirmations,
    db_audit_log,
    db_menu_forecast,
)
from backend.utils.auth import get_current_user
from backend.utils.permissions import require_permission

router = APIRouter()

EXPENSE_CATEGORIES = ("bahan", "listrik", "gas", "air", "internet", "honor", "bbm", "lainnya")
TARGET_COST_PER_PORSI = 15000  # IDR — BGN target
SPIKE_THRESHOLD_PCT = 15.0      # % WoW change → alert


# ── 6A — Price Trend Dashboard ──────────────────────────────────────────────


@router.get("/finance/price-trends")
async def price_trends(
    food_code: str,
    days: int = 30,
    kitchen: dict = Depends(require_permission("finance.price_trends")),
):
    """Return historical prices for a single bahan, ordered oldest first."""
    if days < 1 or days > 365:
        raise HTTPException(400, "days must be between 1 and 365")
    cutoff = (date.today() - timedelta(days=days)).isoformat()

    with engine.connect() as c:
        rows = c.execute(text("""
            SELECT changed_at, price, manual_price, source
            FROM food_prices_history
            WHERE food_code = :code
              AND (kitchen_id = :kid OR kitchen_id IS NULL)
              AND changed_at >= :cutoff
            ORDER BY changed_at ASC
        """), {"code": food_code, "kid": kitchen["id"], "cutoff": cutoff}).fetchall()

    return {
        "food_code": food_code,
        "days": days,
        "history": [
            {
                "changed_at": r.changed_at.isoformat() if r.changed_at else None,
                "price": int(r.price or 0),
                "manual_price": int(r.manual_price) if r.manual_price is not None else None,
                "source": r.source,
            }
            for r in rows
        ],
    }


@router.get("/finance/price-trends/summary")
async def price_trends_summary(
    days: int = 30,
    limit: int = 50,
    kitchen: dict = Depends(require_permission("finance.price_trends")),
):
    """Top-N bahan by latest scraped price + their WoW % change.
    Used by the Akuntan dashboard for at-a-glance overview.
    """
    if days < 7 or days > 90:
        raise HTTPException(400, "days must be between 7 and 90")

    week_ago = (date.today() - timedelta(days=7)).isoformat()
    month_ago = (date.today() - timedelta(days=days)).isoformat()

    with engine.connect() as c:
        # Latest price per food_code (active prices for kitchen or global default).
        rows = c.execute(text("""
            SELECT food_code, food_name, price_per_100g, manual_price, source, scraped_at
            FROM food_prices
            WHERE (kitchen_id = :kid OR kitchen_id IS NULL)
              AND price_per_100g > 0
            ORDER BY scraped_at DESC NULLS LAST, id DESC
            LIMIT :n
        """), {"kid": kitchen["id"], "n": limit}).fetchall()

        # Snapshot price 7 days ago (closest history row).
        results = []
        for r in rows:
            current_price = int(r.manual_price) if r.manual_price else int(r.price_per_100g or 0)
            past_row = c.execute(text("""
                SELECT price FROM food_prices_history
                WHERE food_code = :code
                  AND (kitchen_id = :kid OR kitchen_id IS NULL)
                  AND changed_at <= :week_ago
                ORDER BY changed_at DESC LIMIT 1
            """), {"code": r.food_code, "kid": kitchen["id"], "week_ago": week_ago}).first()
            past_price = int(past_row.price or 0) if past_row else current_price
            wow_pct = round(((current_price - past_price) / past_price) * 100, 1) if past_price > 0 else 0
            results.append({
                "food_code": r.food_code,
                "food_name": r.food_name,
                "current_price": current_price,
                "price_7d_ago": past_price,
                "wow_pct": wow_pct,
                "source": r.source,
                "is_manual": r.manual_price is not None,
                "scraped_at": r.scraped_at.isoformat() if r.scraped_at else None,
            })

    return {
        "days": days,
        "items": results,
    }


# ── 6B — Spike Alert ────────────────────────────────────────────────────────


@router.get("/finance/spike-alerts")
async def spike_alerts(
    threshold_pct: float = SPIKE_THRESHOLD_PCT,
    kitchen: dict = Depends(require_permission("finance.price_trends")),
):
    """Bahan dengan WoW % change > threshold. Default 15%."""
    summary = await price_trends_summary(days=30, limit=200, kitchen=kitchen)
    spikes = [it for it in summary["items"] if abs(it.get("wow_pct") or 0) >= threshold_pct]
    spikes.sort(key=lambda x: abs(x.get("wow_pct") or 0), reverse=True)
    return {
        "threshold_pct": threshold_pct,
        "count": len(spikes),
        "alerts": spikes,
    }


# ── 6C — PO Generator from Forecast ────────────────────────────────────────


class GeneratePOBody(BaseModel):
    from_date:  str
    to_date:    str
    supplier_id: Optional[int] = None
    school_id:   Optional[int] = None
    notes:       Optional[str] = None


@router.post("/finance/po/generate-from-forecast", status_code=201)
async def generate_po_from_forecast(
    body: GeneratePOBody,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("po.create")),
):
    """One-click PO from approved menu forecast (Phase 2B)."""
    # Validate dates.
    try:
        date.fromisoformat(body.from_date)
        date.fromisoformat(body.to_date)
    except ValueError:
        raise HTTPException(400, "Invalid date format")

    forecast = db_menu_forecast(kitchen["id"], body.from_date, body.to_date, school_id=body.school_id)
    if not forecast.get("bahan"):
        raise HTTPException(400, "Tidak ada bahan dalam range ini (apakah ada menu approved?)")

    # Default supplier: pick from kitchen if not specified — error if multiple, ok if single.
    supplier_id = body.supplier_id
    if not supplier_id:
        with engine.connect() as c:
            sup_rows = c.execute(
                select(remote_suppliers.c.id).where(
                    (remote_suppliers.c.kitchen_id == kitchen["id"]) &
                    (remote_suppliers.c.is_active.is_(True))
                ).limit(2)
            ).all()
        if len(sup_rows) == 1:
            supplier_id = sup_rows[0].id
        else:
            raise HTTPException(400, "supplier_id wajib diisi (kitchen punya >1 supplier aktif).")

    # Build PO lines from forecast.
    line_total_sum = 0
    lines_to_insert: list[dict] = []
    for bahan_name, info in forecast["bahan"].items():
        grams = int(info.get("grams_total") or 0)
        if grams <= 0:
            continue
        kg = grams / 1000.0
        unit_price = int(info.get("est_cost_idr") or 0) / kg if kg > 0 else 0
        line_total = int(info.get("est_cost_idr") or 0)
        line_total_sum += line_total
        lines_to_insert.append({
            "item_name": bahan_name,
            "item_code": info.get("code"),
            "total_weight_grams": grams,
            "unit": "kg",
            "expected_containers": max(1, round(kg / 10)),  # default 10kg/box
            "unit_price_idr": int(unit_price),
            "line_total_idr": line_total,
        })

    if not lines_to_insert:
        raise HTTPException(400, "Forecast bahan kosong setelah filter.")

    with engine.begin() as c:
        res = c.execute(
            remote_purchase_orders.insert()
            .values(
                kitchen_id=kitchen["id"],
                supplier_id=supplier_id,
                status="draft",
                expected_delivery_date=body.to_date,
                total_amount_idr=line_total_sum,
                notes=body.notes or f"Auto-generated from forecast {body.from_date} to {body.to_date}",
                created_by=user.get("id"),
            )
            .returning(remote_purchase_orders.c.id)
        )
        new_po_id = res.scalar()
        for ln in lines_to_insert:
            c.execute(remote_po_lines.insert().values(po_id=new_po_id, **ln))

    db_audit_log(
        action="po.auto_generated",
        user_id=user.get("id"),
        kitchen_id=kitchen["id"],
        org_id=user.get("org_id"),
        target_type="purchase_order",
        target_id=str(new_po_id),
        after_value={
            "supplier_id": supplier_id,
            "lines": len(lines_to_insert),
            "total_idr": line_total_sum,
            "from_forecast": {"from": body.from_date, "to": body.to_date},
        },
    )
    return {
        "po_id": new_po_id,
        "supplier_id": supplier_id,
        "lines_count": len(lines_to_insert),
        "total_idr": line_total_sum,
        "based_on_menus": forecast.get("menus_analyzed", 0),
    }


# ── 6D — Expense Tracker ────────────────────────────────────────────────────


class ExpenseBody(BaseModel):
    category:       str = Field(..., max_length=20)
    amount_idr:     int = Field(..., ge=0)
    expense_date:   str   # YYYY-MM-DD
    supplier_id:    Optional[int] = None
    po_id:          Optional[int] = None
    evidence_photo: Optional[str] = None
    notes:          Optional[str] = None


@router.get("/finance/expenses")
async def list_expenses(
    from_date: Optional[str] = None,
    to_date:   Optional[str] = None,
    category:  Optional[str] = None,
    kitchen: dict = Depends(require_permission("expense.view")),
):
    with engine.connect() as c:
        q = select(remote_expenses).where(remote_expenses.c.kitchen_id == kitchen["id"])
        if from_date:
            q = q.where(remote_expenses.c.expense_date >= from_date)
        if to_date:
            q = q.where(remote_expenses.c.expense_date <= to_date)
        if category:
            q = q.where(remote_expenses.c.category == category)
        rows = c.execute(q.order_by(remote_expenses.c.expense_date.desc(), remote_expenses.c.id.desc())).all()
    return {
        "expenses": [
            {
                "id": r.id, "category": r.category, "amount_idr": r.amount_idr,
                "expense_date": str(r.expense_date), "supplier_id": r.supplier_id, "po_id": r.po_id,
                "evidence_photo": r.evidence_photo, "notes": r.notes,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.post("/finance/expenses", status_code=201)
async def create_expense(
    body: ExpenseBody,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("expense.create")),
):
    if body.category not in EXPENSE_CATEGORIES:
        raise HTTPException(400, f"category invalid. Valid: {', '.join(EXPENSE_CATEGORIES)}")
    try:
        date.fromisoformat(body.expense_date)
    except ValueError:
        raise HTTPException(400, "expense_date format invalid")

    with engine.begin() as c:
        res = c.execute(
            remote_expenses.insert()
            .values(kitchen_id=kitchen["id"], created_by=user.get("id"), **body.model_dump())
            .returning(remote_expenses.c.id)
        )
        new_id = res.scalar()

    db_audit_log(
        action="expense.create",
        user_id=user.get("id"),
        kitchen_id=kitchen["id"],
        org_id=user.get("org_id"),
        target_type="expense",
        target_id=str(new_id),
        after_value={"category": body.category, "amount_idr": body.amount_idr, "date": body.expense_date},
    )
    return {"id": new_id, **body.model_dump()}


@router.delete("/finance/expenses/{expense_id}")
async def delete_expense(
    expense_id: int,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("expense.edit")),
):
    with engine.begin() as c:
        res = c.execute(
            remote_expenses.delete().where(
                (remote_expenses.c.id == expense_id) &
                (remote_expenses.c.kitchen_id == kitchen["id"])
            )
        )
        if res.rowcount == 0:
            raise HTTPException(404, "Expense tidak ditemukan.")
    db_audit_log(
        action="expense.delete",
        user_id=user.get("id"),
        kitchen_id=kitchen["id"],
        target_type="expense",
        target_id=str(expense_id),
    )
    return {"ok": True}


# ── 6D — Volunteer payments ─────────────────────────────────────────────────


class VolunteerPaymentBody(BaseModel):
    name:          str = Field(..., max_length=150)
    work_date:     str
    hours_worked:  int = Field(0, ge=0)
    hourly_rate:   int = Field(0, ge=0)
    total_amount:  int = Field(..., ge=0)
    notes:         Optional[str] = None


@router.get("/finance/volunteers")
async def list_volunteers(
    from_date: Optional[str] = None,
    to_date:   Optional[str] = None,
    kitchen: dict = Depends(require_permission("volunteer.manage")),
):
    with engine.connect() as c:
        q = select(remote_volunteer_payments).where(remote_volunteer_payments.c.kitchen_id == kitchen["id"])
        if from_date:
            q = q.where(remote_volunteer_payments.c.work_date >= from_date)
        if to_date:
            q = q.where(remote_volunteer_payments.c.work_date <= to_date)
        rows = c.execute(q.order_by(remote_volunteer_payments.c.work_date.desc())).all()
    return {
        "volunteers": [
            {
                "id": r.id, "name": r.name, "work_date": str(r.work_date),
                "hours_worked": r.hours_worked, "hourly_rate": r.hourly_rate,
                "total_amount": r.total_amount, "notes": r.notes,
            }
            for r in rows
        ],
    }


@router.post("/finance/volunteers", status_code=201)
async def create_volunteer_payment(
    body: VolunteerPaymentBody,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("volunteer.manage")),
):
    with engine.begin() as c:
        res = c.execute(
            remote_volunteer_payments.insert()
            .values(kitchen_id=kitchen["id"], created_by=user.get("id"), **body.model_dump())
            .returning(remote_volunteer_payments.c.id)
        )
        new_id = res.scalar()
    return {"id": new_id, **body.model_dump()}


# ── 6D — Cost-per-porsi calculator ──────────────────────────────────────────


def _calc_cost_per_porsi(kitchen_id: int, from_date: str, to_date: str) -> dict:
    """(total expense + volunteer honor) / total porsi distribusi in date range."""
    with engine.connect() as c:
        # Sum expenses by category.
        exp_rows = c.execute(text("""
            SELECT category, COALESCE(SUM(amount_idr), 0) AS total
            FROM expenses
            WHERE kitchen_id = :kid AND expense_date >= :a AND expense_date <= :b
            GROUP BY category
        """), {"kid": kitchen_id, "a": from_date, "b": to_date}).fetchall()
        expenses_by_category = {r.category: int(r.total or 0) for r in exp_rows}

        # Volunteer payments (separate from honor expense bucket; sum into honor).
        vol_total = c.execute(text("""
            SELECT COALESCE(SUM(total_amount), 0) FROM volunteer_payments
            WHERE kitchen_id = :kid AND work_date >= :a AND work_date <= :b
        """), {"kid": kitchen_id, "a": from_date, "b": to_date}).scalar() or 0
        if vol_total:
            expenses_by_category["honor"] = expenses_by_category.get("honor", 0) + int(vol_total)

        # Total porsi distribusi from delivery_confirmations.
        porsi = c.execute(text("""
            SELECT COALESCE(SUM(confirmed_count), 0) FROM delivery_confirmations
            WHERE kitchen_id = :kid AND DATE(confirmed_at) >= :a AND DATE(confirmed_at) <= :b
        """), {"kid": kitchen_id, "a": from_date, "b": to_date}).scalar() or 0

    total_expense = sum(expenses_by_category.values())
    cost_per_porsi = int(round(total_expense / porsi)) if porsi > 0 else 0
    return {
        "from_date": from_date,
        "to_date": to_date,
        "expenses_by_category": expenses_by_category,
        "total_expense_idr": total_expense,
        "total_porsi_confirmed": int(porsi),
        "cost_per_porsi_idr": cost_per_porsi,
        "target_idr": TARGET_COST_PER_PORSI,
        "over_target": cost_per_porsi > TARGET_COST_PER_PORSI,
    }


@router.get("/finance/cost-per-porsi")
async def cost_per_porsi(
    from_date: str,
    to_date: str,
    kitchen: dict = Depends(require_permission("finance.view")),
):
    try:
        date.fromisoformat(from_date)
        date.fromisoformat(to_date)
    except ValueError:
        raise HTTPException(400, "Invalid date format")
    return _calc_cost_per_porsi(kitchen["id"], from_date, to_date)


# ── 6D — LRA Biweekly ───────────────────────────────────────────────────────


class LRAGenerateBody(BaseModel):
    period_start:      str
    period_end:        str
    total_revenue_idr: int = Field(0, ge=0)
    notes:             Optional[str] = None


@router.get("/finance/lra/periods")
async def list_lra_periods(kitchen: dict = Depends(require_permission("lra.view"))):
    with engine.connect() as c:
        rows = c.execute(
            select(remote_lra_periods).where(remote_lra_periods.c.kitchen_id == kitchen["id"])
            .order_by(remote_lra_periods.c.period_start.desc())
        ).all()
    return {
        "periods": [
            {
                "id": r.id, "period_start": str(r.period_start), "period_end": str(r.period_end),
                "status": r.status, "total_revenue_idr": r.total_revenue_idr,
                "total_expense_idr": r.total_expense_idr, "total_porsi": r.total_porsi,
                "cost_per_porsi": r.cost_per_porsi,
                "generated_at": r.generated_at.isoformat() if r.generated_at else None,
                "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
            }
            for r in rows
        ],
    }


@router.get("/finance/lra/periods/{period_id}")
async def get_lra_period(
    period_id: int,
    kitchen: dict = Depends(require_permission("lra.view")),
):
    import json as _json
    with engine.connect() as c:
        row = c.execute(
            select(remote_lra_periods).where(
                (remote_lra_periods.c.id == period_id) &
                (remote_lra_periods.c.kitchen_id == kitchen["id"])
            )
        ).first()
    if not row:
        raise HTTPException(404, "LRA period tidak ditemukan.")
    out = dict(row._mapping)
    out["period_start"] = str(out["period_start"])
    out["period_end"] = str(out["period_end"])
    if out.get("breakdown_json"):
        try:
            out["breakdown"] = _json.loads(out["breakdown_json"])
        except Exception:
            out["breakdown"] = {}
    out["generated_at"] = out["generated_at"].isoformat() if out["generated_at"] else None
    out["submitted_at"] = out["submitted_at"].isoformat() if out["submitted_at"] else None
    return out


@router.post("/finance/lra/generate", status_code=201)
async def generate_lra(
    body: LRAGenerateBody,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("lra.generate")),
):
    """Snapshot expenses + porsi for the period → create lra_periods row."""
    import json as _json
    try:
        date.fromisoformat(body.period_start)
        date.fromisoformat(body.period_end)
    except ValueError:
        raise HTTPException(400, "Invalid date format")
    if body.period_start > body.period_end:
        raise HTTPException(400, "period_start must be ≤ period_end")

    snapshot = _calc_cost_per_porsi(kitchen["id"], body.period_start, body.period_end)
    breakdown_json = _json.dumps(snapshot, ensure_ascii=False)

    with engine.begin() as c:
        res = c.execute(
            remote_lra_periods.insert()
            .values(
                kitchen_id=kitchen["id"],
                period_start=body.period_start,
                period_end=body.period_end,
                status="generated",
                total_revenue_idr=body.total_revenue_idr,
                total_expense_idr=snapshot["total_expense_idr"],
                total_porsi=snapshot["total_porsi_confirmed"],
                cost_per_porsi=snapshot["cost_per_porsi_idr"],
                breakdown_json=breakdown_json,
                notes=body.notes,
                generated_by=user.get("id"),
                generated_at=datetime.now(),
            )
            .returning(remote_lra_periods.c.id)
        )
        new_id = res.scalar()

    db_audit_log(
        action="lra.generate",
        user_id=user.get("id"),
        kitchen_id=kitchen["id"],
        org_id=user.get("org_id"),
        target_type="lra",
        target_id=str(new_id),
        after_value={
            "period": f"{body.period_start} to {body.period_end}",
            "total_expense": snapshot["total_expense_idr"],
            "total_porsi": snapshot["total_porsi_confirmed"],
            "cost_per_porsi": snapshot["cost_per_porsi_idr"],
        },
    )
    return await get_lra_period(period_id=new_id, kitchen=kitchen)


@router.post("/finance/lra/periods/{period_id}/submit")
async def submit_lra(
    period_id: int,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("lra.signoff")),
):
    """Head SPPG signs-off the LRA → mark submitted (audit only — actual file
    upload to PPK BGN is handled outside the system)."""
    with engine.begin() as c:
        res = c.execute(
            remote_lra_periods.update()
            .where(
                (remote_lra_periods.c.id == period_id) &
                (remote_lra_periods.c.kitchen_id == kitchen["id"])
            )
            .values(status="submitted", submitted_at=datetime.now())
        )
        if res.rowcount == 0:
            raise HTTPException(404, "LRA period tidak ditemukan.")
    db_audit_log(
        action="lra.submit",
        user_id=user.get("id"),
        kitchen_id=kitchen["id"],
        org_id=user.get("org_id"),
        target_type="lra",
        target_id=str(period_id),
    )
    return await get_lra_period(period_id=period_id, kitchen=kitchen)
