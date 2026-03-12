import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.utils.auth import get_current_user
from backend.services.menu_optimizer import load_tkpi, optimize_week, DEFAULT_CONSTRAINTS, AKG_PRESETS, NUTRIENT_KEYS
from backend.services.price_scraper import get_prices
from backend.core.database import db_get_food_prices, db_get_price_scrape_status

router = APIRouter()

TKPI_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "tkpi.csv",
)


class GroupInput(BaseModel):
    label: str                          # e.g. "SD (7-9 tahun)"
    num_students: int = 1
    constraints: Optional[dict] = None  # if None, uses AKG_PRESETS[label] or DEFAULT_CONSTRAINTS


class OptimizeRequest(BaseModel):
    num_days: int = 5
    num_students: int = 100             # used only when groups is None (legacy)
    constraints: Optional[dict] = None  # used only when groups is None (legacy)
    groups: Optional[list[GroupInput]] = None
    excluded_foods: Optional[list[str]] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    budget_min: Optional[float] = None  # IDR per serving, minimum cost constraint


def _build_group_result(foods, body: OptimizeRequest, group: GroupInput):
    c = dict(group.constraints or AKG_PRESETS.get(group.label) or DEFAULT_CONSTRAINTS)
    if body.budget_min and body.budget_min > 0:
        c["min_cost"] = body.budget_min
    week = optimize_week(
        foods,
        num_days=min(body.num_days, 7),
        constraints=c,
        excluded_foods=body.excluded_foods,
    )
    feasible = [d for d in week if d.get("feasible")]
    weekly_cost = sum(d.get("cost_per_serving", 0) for d in week)
    avg_nutrition = {}
    if feasible:
        for key in NUTRIENT_KEYS:
            avg_nutrition[key] = round(
                sum(d["nutrition"][key] for d in feasible) / len(feasible), 1
            )
    return {
        "label": group.label,
        "num_students": group.num_students,
        "week": week,
        "weekly_per_student": round(weekly_cost),
        "weekly_total": round(weekly_cost * group.num_students),
        "avg_nutrition": avg_nutrition,
        "constraints_used": {**DEFAULT_CONSTRAINTS, **c},
    }


@router.post("/menu/optimize")
async def optimize_menu(body: OptimizeRequest, user: dict = Depends(get_current_user)):
    if not os.path.isfile(TKPI_PATH):
        raise HTTPException(500, "TKPI data file not found. Place tkpi.csv in data/")

    try:
        db_prices = db_get_food_prices()
    except Exception:
        db_prices = {}

    foods = load_tkpi(TKPI_PATH, db_prices=db_prices)
    if not foods:
        raise HTTPException(500, "No usable food items. Run the price scraper first to populate prices.")

    if body.price_min is not None and body.price_min > 0:
        foods = [f for f in foods if f["price"] >= body.price_min]
    if body.price_max is not None and body.price_max > 0:
        foods = [f for f in foods if f["price"] <= body.price_max]

    # Multi-group mode
    if body.groups:
        groups_result = [_build_group_result(foods, body, g) for g in body.groups]
        total_students = sum(g.num_students for g in body.groups)
        grand_total = sum(r["weekly_total"] for r in groups_result)
        return {
            "mode": "multi_group",
            "groups": groups_result,
            "total_students": total_students,
            "grand_total": round(grand_total),
            "prices_from_db": len(db_prices),
        }

    # Legacy single-group mode
    legacy_c = dict(body.constraints or {})
    if body.budget_min and body.budget_min > 0:
        legacy_c["min_cost"] = body.budget_min
    week = optimize_week(
        foods,
        num_days=min(body.num_days, 7),
        constraints=legacy_c or None,
        excluded_foods=body.excluded_foods,
    )
    weekly_cost_per_student = sum(d.get("cost_per_serving", 0) for d in week)
    weekly_total = weekly_cost_per_student * body.num_students
    feasible = [d for d in week if d.get("feasible")]
    avg_nutrition = {}
    if feasible:
        for key in NUTRIENT_KEYS:
            avg_nutrition[key] = round(
                sum(d["nutrition"][key] for d in feasible) / len(feasible), 1
            )
    return {
        "mode": "single",
        "week": week,
        "num_students": body.num_students,
        "weekly_per_student": round(weekly_cost_per_student),
        "weekly_total": round(weekly_total),
        "avg_nutrition": avg_nutrition,
        "constraints_used": {**DEFAULT_CONSTRAINTS, **(body.constraints or {})},
        "prices_from_db": len(db_prices),
    }


@router.get("/menu/akg-presets")
async def get_akg_presets(_user: dict = Depends(get_current_user)):
    return AKG_PRESETS


@router.get("/menu/foods")
async def list_foods(_user: dict = Depends(get_current_user)):
    """Return all TKPI foods (with DB prices overlaid) grouped by category."""
    if not os.path.isfile(TKPI_PATH):
        raise HTTPException(500, "TKPI data file not found.")

    try:
        db_prices = db_get_food_prices()
    except Exception:
        db_prices = {}

    # Load all items (even price=0 ones) for display
    import csv, re
    all_foods = []
    def _sf(v):
        if not v or str(v).strip() in ("", "-", "Tr", "tr"): return 0.0
        try: return float(re.sub(r"[^\d.\-]", "", str(v).strip()))
        except: return 0.0

    from backend.services.menu_optimizer import categorize_food
    with open(TKPI_PATH, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            code = (row.get("KODE") or "").strip()
            name = (row.get("NAMA BAHAN") or "").strip()
            if not code or not name: continue
            price = float(db_prices.get(code, 0))
            energy = _sf(row.get("ENERGI"))
            if energy <= 0: continue
            all_foods.append({
                "code": code,
                "name": name,
                "price": price,
                "has_price": price > 0,
                "energy": energy,
                "protein": _sf(row.get("PROTEIN")),
                "category": categorize_food(code, name),
            })

    by_category: dict = {}
    for f in all_foods:
        cat = f["category"]
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(f)

    return {
        "categories": by_category,
        "total": len(all_foods),
        "with_price": sum(1 for f in all_foods if f["has_price"]),
        "without_price": sum(1 for f in all_foods if not f["has_price"]),
    }


@router.get("/menu/prices/status")
async def price_scrape_status(_user: dict = Depends(get_current_user)):
    """Return all scraped prices and last scrape time."""
    try:
        rows = db_get_price_scrape_status()
        return {
            "count": len(rows),
            "prices": [
                {
                    "code": r["food_code"],
                    "name": r["food_name"],
                    "price_per_100g": r["price_per_100g"],
                    "source": r["source"],
                    "scraped_at": str(r["scraped_at"]) if r["scraped_at"] else None,
                }
                for r in rows[:200]
            ],
        }
    except Exception as e:
        raise HTTPException(500, str(e))


class PriceRequest(BaseModel):
    keywords: list[str]


@router.post("/menu/prices")
async def fetch_prices(body: PriceRequest, _user: dict = Depends(get_current_user)):
    """
    Fetch market prices for a list of ingredient keywords from Sayurbox.
    Slow (~8s per keyword) — use the scheduled scraper instead for bulk operations.
    """
    if not body.keywords:
        raise HTTPException(400, "keywords list is empty")
    if len(body.keywords) > 20:
        raise HTTPException(400, "Max 20 keywords per request")

    prices = get_prices(body.keywords)
    return {
        "prices": {kw: p for kw, p in prices.items()},
        "found": sum(1 for p in prices.values() if p is not None),
        "not_found": [kw for kw, p in prices.items() if p is None],
    }
