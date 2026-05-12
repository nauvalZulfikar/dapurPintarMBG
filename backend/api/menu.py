import os
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.utils.auth import get_current_user, get_current_kitchen
from backend.utils.permissions import require_permission
from backend.services.menu_optimizer import load_tkpi, optimize_week, DEFAULT_CONSTRAINTS, AKG_PRESETS, NUTRIENT_KEYS
from backend.services.price_scraper import get_prices
from backend.core.database import (
    db_get_food_prices, db_get_price_scrape_status,
    db_list_nutrition_overrides, db_upsert_nutrition_override,
    db_delete_nutrition_override,
    db_log_price_change, db_get_price_history,
    db_menu_cycle_check, db_menu_forecast,
)

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
async def optimize_menu(body: OptimizeRequest, kitchen: dict = Depends(require_permission("menu.optimize"))):
    if not os.path.isfile(TKPI_PATH):
        raise HTTPException(500, "TKPI data file not found. Place tkpi.csv in data/")

    try:
        db_prices = db_get_food_prices(kitchen_id=kitchen["id"])
    except Exception:
        db_prices = {}
    try:
        nutr_overrides = db_list_nutrition_overrides(kitchen_id=kitchen["id"])
    except Exception:
        nutr_overrides = {}

    foods = load_tkpi(TKPI_PATH, db_prices=db_prices, nutrition_overrides=nutr_overrides)
    if not foods:
        raise HTTPException(500, "No usable food items. Run the price scraper first to populate prices.")

    if body.price_min is not None and body.price_min > 0:
        foods = [f for f in foods if f["price"] >= body.price_min]
    if body.price_max is not None and body.price_max > 0:
        foods = [f for f in foods if f["price"] <= body.price_max]

    # Multi-group mode
    if body.groups:
        with ThreadPoolExecutor(max_workers=len(body.groups)) as ex:
            futures = [ex.submit(_build_group_result, foods, body, g) for g in body.groups]
            groups_result = [f.result() for f in futures]
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


# ── Phase 2A — Reverse Optimizer (manual menu input → auto-calc nutrition) ──

class ManualMenuItem(BaseModel):
    code: str                         # TKPI food code
    grams: float = 0


class ManualMenuCalcRequest(BaseModel):
    items: list[ManualMenuItem]
    age_group: Optional[str] = None   # AKG preset key, e.g. "SD (7-9 tahun)"


@router.post("/menu/calc")
async def calc_manual_menu(
    body: ManualMenuCalcRequest,
    kitchen: dict = Depends(require_permission("menu.calc")),
):
    """Reverse mode: given a manual list of (food_code, grams), return total
    nutrition + cost + AKG comparison. Used by the "Build Menu Manual" tab
    in the Menu Planner. Reuses TKPI loader, price scrape, AKG presets, and
    `categorize_food` — no new data sources.
    """
    if not os.path.isfile(TKPI_PATH):
        raise HTTPException(500, "TKPI data file not found. Place tkpi.csv in data/")

    if not body.items:
        raise HTTPException(400, "items list is empty")

    try:
        db_prices = db_get_food_prices(kitchen_id=kitchen["id"])
    except Exception:
        db_prices = {}
    try:
        nutr_overrides = db_list_nutrition_overrides(kitchen_id=kitchen["id"])
    except Exception:
        nutr_overrides = {}

    foods = load_tkpi(TKPI_PATH, db_prices=db_prices, nutrition_overrides=nutr_overrides)
    by_code = {f["code"]: f for f in foods}

    # Per-item breakdown (skip items with 0 grams; warn on missing codes).
    per_item: list[dict] = []
    missing: list[str] = []
    totals = {k: 0.0 for k in NUTRIENT_KEYS}
    total_cost = 0.0

    for it in body.items:
        if it.grams <= 0:
            continue
        f = by_code.get(it.code)
        if not f:
            missing.append(it.code)
            continue
        # Per-100g values × (grams / 100) — matches optimize_day math.
        scale = it.grams / 100.0
        item_nutr = {k: round(f.get(k, 0) * scale, 2) for k in NUTRIENT_KEYS}
        item_cost = round(f.get("price", 0) * scale, 1)
        for k in NUTRIENT_KEYS:
            totals[k] += item_nutr[k]
        total_cost += item_cost
        per_item.append({
            "code": f["code"],
            "name": f["name"],
            "category": f["category"],
            "grams": round(it.grams, 1),
            "cost": item_cost,
            "nutrition": item_nutr,
        })

    totals = {k: round(v, 2) for k, v in totals.items()}
    total_cost = round(total_cost)

    # Compare against AKG preset if provided.
    akg = AKG_PRESETS.get(body.age_group) if body.age_group else None
    akg_compare = None
    if akg:
        akg_compare = {}
        # min_* checks: cukup kalau total >= min
        for nutr_key, akg_min_key in [
            ("energy",  "min_energy"),
            ("protein", "min_protein"),
            ("carbs",   "min_carbs"),
            ("fiber",   "min_fiber"),
            ("iron",    "min_iron"),
            ("vitc",    "min_vitc"),
        ]:
            if akg_min_key in akg:
                target = akg[akg_min_key]
                actual = totals.get(nutr_key, 0)
                pct = round((actual / target) * 100, 1) if target > 0 else 0
                akg_compare[nutr_key] = {
                    "actual": actual,
                    "target": target,
                    "kind": "min",
                    "pct": pct,
                    "status": "ok" if actual >= target else "low",
                }
        # max_fat: cukup kalau total <= max
        if "max_fat" in akg:
            target = akg["max_fat"]
            actual = totals.get("fat", 0)
            akg_compare["fat"] = {
                "actual": actual,
                "target": target,
                "kind": "max",
                "pct": round((actual / target) * 100, 1) if target > 0 else 0,
                "status": "ok" if actual <= target else "high",
            }

    return {
        "items": per_item,
        "missing_codes": missing,
        "totals": totals,
        "cost_per_serving": total_cost,
        "age_group": body.age_group,
        "akg_compare": akg_compare,
    }


@router.get("/menu/cycle-check")
async def menu_cycle_check(
    days: int = 20,
    kitchen: dict = Depends(require_permission("menu.cycle_check")),
):
    """Phase 2B — BGN siklus 20 hari analyzer. Returns frequency of key bahan
    in approved/locked menus over the last `days` days, plus warnings if any
    bahan exceeds BGN limit (telur ≤8x, ayam ≤8x, tahu ≤10x, tempe ≤10x).
    """
    if days < 1 or days > 90:
        raise HTTPException(400, "days must be between 1 and 90")
    return db_menu_cycle_check(kitchen["id"], days=days)


class ForecastQuery(BaseModel):
    from_date: str
    to_date:   str
    school_id: Optional[int] = None


@router.get("/menu/forecast")
async def menu_forecast(
    from_date: str,
    to_date: str,
    school_id: Optional[int] = None,
    kitchen: dict = Depends(require_permission("menu.forecast")),
):
    """Phase 2B — sum bahan needs from approved menus in [from_date, to_date].

    Output feeds Phase 6 (Akuntan PO generator) and Phase 3 (Joint Inspection
    PO checklist). Multiplier = student_count of target school (or sum of all
    active schools if menu has no target).
    """
    from datetime import date as _date
    try:
        _date.fromisoformat(from_date)
        _date.fromisoformat(to_date)
    except ValueError:
        raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD.")
    if from_date > to_date:
        raise HTTPException(400, "from_date must be ≤ to_date")
    return db_menu_forecast(kitchen["id"], from_date, to_date, school_id=school_id)


@router.get("/menu/foods")
async def list_foods(kitchen: dict = Depends(require_permission("menu.view"))):
    """Return all TKPI foods (with DB prices overlaid) grouped by category."""
    if not os.path.isfile(TKPI_PATH):
        raise HTTPException(500, "TKPI data file not found.")

    try:
        db_prices = db_get_food_prices(kitchen_id=kitchen["id"])
    except Exception:
        db_prices = {}
    try:
        nutr_overrides = db_list_nutrition_overrides(kitchen_id=kitchen["id"])
    except Exception:
        nutr_overrides = {}

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
            protein = _sf(row.get("PROTEIN"))
            # apply nutrition overrides
            ov = nutr_overrides.get(code) or {}
            if "energy" in ov:
                try: energy = float(ov["energy"])
                except (TypeError, ValueError): pass
            if "protein" in ov:
                try: protein = float(ov["protein"])
                except (TypeError, ValueError): pass
            if energy <= 0: continue
            all_foods.append({
                "code": code,
                "name": name,
                "price": price,
                "has_price": price > 0,
                "energy": energy,
                "protein": protein,
                "has_nutrition_override": bool(ov),
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
async def price_scrape_status(kitchen: dict = Depends(require_permission("menu.view"))):
    """Return all scraped prices (with manual overrides) and last scrape time."""
    try:
        rows = db_get_price_scrape_status(kitchen_id=kitchen["id"])
        return {
            "count": len(rows),
            "prices": [
                {
                    "code": r["food_code"],
                    "name": r["food_name"],
                    "price_per_100g": r["price_per_100g"],
                    "manual_price": r.get("manual_price"),
                    "manual_source": r.get("manual_source"),
                    "manual_set_at": str(r["manual_set_at"]) if r.get("manual_set_at") else None,
                    "effective_price": r.get("manual_price") if r.get("manual_price") is not None else r["price_per_100g"],
                    "source": r["source"],
                    "scraped_at": str(r["scraped_at"]) if r["scraped_at"] else None,
                }
                for r in rows[:500]
            ],
        }
    except Exception as e:
        raise HTTPException(500, str(e))


class ManualPriceBody(BaseModel):
    price: Optional[int] = None            # IDR per 100g; null to clear override
    manual_source: Optional[str] = None    # e.g. "invoice #1234" or supplier name
    food_name: Optional[str] = None        # fallback if row doesn't exist yet


@router.patch("/menu/prices/{food_code}")
async def override_price(
    food_code: str,
    body: ManualPriceBody,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("prices.override")),
):
    """Set (or clear with price=null) a per-kitchen manual price for `food_code`.

    Accountant / admin only. Falls back to scraped price when cleared.
    """
    from backend.core.database import engine, remote_food_prices
    from sqlalchemy import select, text as _text
    from datetime import datetime

    with engine.begin() as c:
        row = c.execute(
            select(remote_food_prices.c.id)
            .where(
                (remote_food_prices.c.food_code == food_code) &
                (remote_food_prices.c.kitchen_id == kitchen["id"])
            )
        ).first()
        if row:
            c.execute(_text("""
                UPDATE food_prices SET
                    manual_price   = :p,
                    manual_source  = :src,
                    manual_set_by  = :uid,
                    manual_set_at  = :ts,
                    updated_at     = :ts
                WHERE id = :rid
            """), {
                "p": body.price, "src": body.manual_source,
                "uid": user["id"], "ts": datetime.now(), "rid": row.id,
            })
        else:
            if body.price is None:
                raise HTTPException(404, "No price row to clear")
            c.execute(_text("""
                INSERT INTO food_prices
                    (kitchen_id, food_code, food_name, price_per_100g,
                     manual_price, manual_source, manual_set_by, manual_set_at,
                     source, updated_at)
                VALUES (:kid, :code, :name, 0, :p, :src, :uid, :ts, 'manual', :ts)
            """), {
                "kid": kitchen["id"], "code": food_code,
                "name": body.food_name or body.food_name or food_code,
                "p": body.price, "src": body.manual_source,
                "uid": user["id"], "ts": datetime.now(),
            })

    # Log the change for accountant audit trail
    try:
        db_log_price_change(
            kitchen_id=kitchen["id"], food_code=food_code,
            price=body.price, manual_price=body.price,
            source="manual" if body.price is not None else "manual_clear",
            user_id=user["id"],
        )
    except Exception:
        pass  # don't fail the mutation if audit log write fails
    return {"ok": True, "food_code": food_code, "manual_price": body.price}


# ── Food nutrition override (ahli_gizi / admin) ──────────────────────────────

class NutritionOverrideBody(BaseModel):
    overrides: dict  # free-form {field: value}, only keys in allowed list are saved

ALLOWED_NUTR_KEYS = {
    "energy", "protein", "fat", "carb", "fiber",
    "calcium", "iron", "vitamin_a", "vitamin_c",
    "zinc", "sodium", "water", "ash",
}


@router.get("/menu/foods/overrides")
async def list_nutrition_overrides(kitchen: dict = Depends(require_permission("menu.view"))):
    """Return {food_code: overrides_dict} for the active kitchen."""
    return {"overrides": db_list_nutrition_overrides(kitchen_id=kitchen["id"])}


@router.patch("/menu/foods/{food_code}/override")
async def set_nutrition_override(
    food_code: str,
    body: NutritionOverrideBody,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("foods.edit")),
):
    """Upsert per-kitchen nutrition override for a food_code.
    Only whitelisted keys are saved; others are dropped silently.
    """
    clean: dict = {}
    for k, v in (body.overrides or {}).items():
        if k not in ALLOWED_NUTR_KEYS:
            continue
        try:
            clean[k] = float(v)
        except (TypeError, ValueError):
            pass
    if not clean:
        raise HTTPException(400, f"No valid override fields. Allowed: {sorted(ALLOWED_NUTR_KEYS)}")
    db_upsert_nutrition_override(
        kitchen_id=kitchen["id"],
        food_code=food_code,
        overrides=clean,
        user_id=user["id"],
    )
    return {"ok": True, "food_code": food_code, "overrides": clean}


@router.delete("/menu/foods/{food_code}/override")
async def clear_nutrition_override(
    food_code: str,
    kitchen: dict = Depends(require_permission("foods.edit")),
):
    n = db_delete_nutrition_override(kitchen_id=kitchen["id"], food_code=food_code)
    return {"ok": True, "deleted": n}


# ── Price history (accountant / admin) ───────────────────────────────────────

@router.get("/menu/prices/{food_code}/history")
async def price_history(
    food_code: str,
    kitchen: dict = Depends(require_permission("prices.history")),
):
    rows = db_get_price_history(kitchen_id=kitchen["id"], food_code=food_code, limit=100)
    return {
        "food_code": food_code,
        "history": [
            {
                "price": r["price"],
                "manual_price": r["manual_price"],
                "source": r["source"],
                "changed_by": r["changed_by"],
                "changed_at": str(r["changed_at"]) if r["changed_at"] else None,
            }
            for r in rows
        ],
    }


# ── Food substitutes (cosine similarity on TKPI vectors) ─────────────────────

import math as _math

_TKPI_CACHE = None


def _cosine_sim(a: list, b: list) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = _math.sqrt(sum(x ** 2 for x in a))
    mag_b = _math.sqrt(sum(x ** 2 for x in b))
    return dot / (mag_a * mag_b + 1e-9)


def _compute_substitutes(food_name: str, kitchen_id: int) -> list[dict]:
    """Find top-5 TKPI foods most similar to food_name by cosine sim on [energy, protein, fat, carbs]."""
    import csv as _csv, re as _re

    def _sf(v):
        if not v or str(v).strip() in ("", "-", "Tr", "tr", "NA", "na"): return 0.0
        try: return float(_re.sub(r"[^\d.\-]", "", str(v).strip()))
        except: return 0.0

    from backend.services.menu_optimizer import categorize_food

    global _TKPI_CACHE
    if _TKPI_CACHE is None:
        loaded = []
        with open(TKPI_PATH, "r", encoding="utf-8-sig") as f:
            for row in _csv.DictReader(f):
                code = (row.get("KODE") or "").strip()
                name = (row.get("NAMA BAHAN") or "").strip()
                if not code or not name:
                    continue
                loaded.append({
                    "code": code,
                    "name": name,
                    "category": categorize_food(code, name),
                    "energy":  _sf(row.get("ENERGI")),
                    "protein": _sf(row.get("PROTEIN")),
                    "fat":     _sf(row.get("LEMAK")),
                    "carbs":   _sf(row.get("KH")),
                })
        _TKPI_CACHE = loaded
    all_foods = _TKPI_CACHE

    q = food_name.strip().lower()
    target = next((f for f in all_foods if f["name"].lower() == q), None)
    if not target:
        target = next((f for f in all_foods if q in f["name"].lower()), None)
    if not target:
        return []

    target_vec = [target["energy"], target["protein"], target["fat"], target["carbs"]]
    if _math.sqrt(sum(x ** 2 for x in target_vec)) < 1e-9:
        return []

    candidates = []
    for f in all_foods:
        if f["code"] == target["code"]:
            continue
        vec = [f["energy"], f["protein"], f["fat"], f["carbs"]]
        if _math.sqrt(sum(x ** 2 for x in vec)) < 1e-9:
            continue
        sim = _cosine_sim(target_vec, vec)
        candidates.append({**f, "similarity": sim})

    same_cat = sorted([c for c in candidates if c["category"] == target["category"]], key=lambda x: -x["similarity"])
    other_cat = sorted([c for c in candidates if c["category"] != target["category"]], key=lambda x: -x["similarity"])

    top5 = (same_cat + other_cat)[:5]
    return [
        {
            "code": f["code"],
            "name": f["name"],
            "category": f["category"],
            "similarity": round(f["similarity"], 2),
            "similarity_score": round(f["similarity"], 2),
            "nutrition": {
                "energy":  f["energy"],
                "protein": f["protein"],
                "fat":     f["fat"],
                "carbs":   f["carbs"],
            },
        }
        for f in top5
    ]


@router.get("/menu/substitutes")
async def get_substitutes(
    food_name: str,
    kitchen: dict = Depends(require_permission("menu.view")),
):
    if not os.path.isfile(TKPI_PATH):
        raise HTTPException(500, "TKPI data file not found.")
    substitutes = _compute_substitutes(food_name, kitchen["id"])
    return {"food_name": food_name, "substitutes": substitutes}


class PriceRequest(BaseModel):
    keywords: list[str]


@router.post("/menu/prices")
async def fetch_prices(body: PriceRequest, kitchen: dict = Depends(require_permission("menu.scrape"))):
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
