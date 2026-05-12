from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.utils.permissions import require_permission
from backend.core.database import db_get_nutrition_daily, db_get_nutrition_weekly

router = APIRouter()


@router.get("/nutrition/daily")
async def nutrition_daily(
    date_param: Optional[str] = Query(None, alias="date"),
    kitchen: dict = Depends(require_permission("nutrition.report")),
):
    target = date_param or str(date.today())
    try:
        date.fromisoformat(target)
    except ValueError:
        raise HTTPException(400, "Format tanggal tidak valid. Gunakan YYYY-MM-DD.")
    return db_get_nutrition_daily(kitchen["id"], target)


@router.get("/nutrition/weekly-compliance")
async def nutrition_weekly_compliance(
    week_start: Optional[str] = Query(None),
    kitchen: dict = Depends(require_permission("nutrition.report")),
):
    if week_start:
        try:
            d_start = date.fromisoformat(week_start)
        except ValueError:
            raise HTTPException(400, "Format tanggal tidak valid. Gunakan YYYY-MM-DD.")
    else:
        today = date.today()
        d_start = today - timedelta(days=today.weekday())

    d_end = d_start + timedelta(days=6)
    days = db_get_nutrition_weekly(kitchen["id"], str(d_start), str(d_end))
    return {
        "week_start": str(d_start),
        "week_end": str(d_end),
        "days": days,
    }
