import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.utils.auth import get_current_user
from backend.services.menu_optimizer import load_tkpi, optimize_week, DEFAULT_CONSTRAINTS, NUTRIENT_KEYS
from backend.services.price_scraper import get_prices

router = APIRouter()

TKPI_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "tkpi.csv",
)


class OptimizeRequest(BaseModel):
    num_days: int = 5
    num_students: int = 100
    constraints: Optional[dict] = None
    excluded_foods: Optional[list[str]] = None


@router.post("/menu/optimize")
async def optimize_menu(body: OptimizeRequest, user: dict = Depends(get_current_user)):
    if not os.path.isfile(TKPI_PATH):
        raise HTTPException(500, "TKPI data file not found. Place tkpi.csv in data/")

    foods = load_tkpi(TKPI_PATH)
    if not foods:
        raise HTTPException(500, "No usable food items in TKPI data.")

    week = optimize_week(
        foods,
        num_days=min(body.num_days, 7),
        constraints=body.constraints,
        excluded_foods=body.excluded_foods,
    )

    # Compute totals
    weekly_cost_per_student = sum(d.get("cost_per_serving", 0) for d in week)
    weekly_total = weekly_cost_per_student * body.num_students

    # Average nutrition across feasible days
    feasible = [d for d in week if d.get("feasible")]
    avg_nutrition = {}
    if feasible:
        for key in NUTRIENT_KEYS:
            avg_nutrition[key] = round(
                sum(d["nutrition"][key] for d in feasible) / len(feasible), 1
            )

    return {
        "week": week,
        "num_students": body.num_students,
        "weekly_per_student": round(weekly_cost_per_student),
        "weekly_total": round(weekly_total),
        "avg_nutrition": avg_nutrition,
        "constraints_used": {**DEFAULT_CONSTRAINTS, **(body.constraints or {})},
    }


@router.get("/menu/foods")
async def list_foods(user: dict = Depends(get_current_user)):
    """Return all TKPI foods grouped by category for the UI."""
    if not os.path.isfile(TKPI_PATH):
        raise HTTPException(500, "TKPI data file not found.")

    foods = load_tkpi(TKPI_PATH)
    by_category = {}
    for f in foods:
        cat = f["category"]
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append({
            "code": f["code"],
            "name": f["name"],
            "price": f["price"],
            "energy": f["energy"],
            "protein": f["protein"],
        })

    return {"categories": by_category, "total": len(foods)}


class PriceRequest(BaseModel):
    keywords: list[str]


@router.post("/menu/prices")
async def fetch_prices(body: PriceRequest, _user: dict = Depends(get_current_user)):
    """
    Fetch market prices for a list of ingredient keywords from
    Happyfresh, Segari, and Sayurbox, then return the average per 100g (IDR).
    This is slow (~1-2s per keyword) — call sparingly.
    """
    if not body.keywords:
        raise HTTPException(400, "keywords list is empty")
    if len(body.keywords) > 50:
        raise HTTPException(400, "Max 50 keywords per request")

    prices = get_prices(body.keywords)
    return {
        "prices": {kw: p for kw, p in prices.items()},
        "found": sum(1 for p in prices.values() if p is not None),
        "not_found": [kw for kw, p in prices.items() if p is None],
    }
