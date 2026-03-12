"""
Menu optimizer — linear programming for MBG school meals.

Uses PuLP to solve the classic "diet problem":
  minimize cost  subject to  AKG nutritional constraints.
"""

import csv
import os
import re
from typing import Optional

from pulp import (
    LpProblem, LpMinimize, LpVariable, lpSum, value,
    PULP_CBC_CMD, LpStatusOptimal,
)

# ── TKPI loader ──────────────────────────────────────────────────────────────

TKPI_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "tkpi.csv",
)

# Column name mapping (tkpi.csv headers → internal keys)
COL_MAP = {
    "KODE":                   "code",
    "NAMA BAHAN":             "name",
    "BERAT STANDAR":          "berat_standar",
    "BDD":                    "bdd",
    "ENERGI":                 "energy",
    "PROTEIN":                "protein",
    "LEMAK":                  "fat",
    "KH":                     "carbs",
    "SERAT":                  "fiber",
    "BESI":                   "iron",
    "VIT_C":                  "vitc",
    "KALSIUM":                "calcium",
    "FOSFOR":                 "fosfor",
    "NATRIUM":                "natrium",
    "KALIUM":                 "kalium",
    "SENG":                   "seng",
    "THIAMIN":                "thiamin",
    "RIBOFLAVIN":             "riboflavin",
    "NIASIN":                 "niasin",
    "RETINOL":                "retinol",
    "HARGA PER-BERAT STANDAR": "price",  # IDR per berat standar (100g default)
}

NUTRIENT_KEYS = ["energy", "protein", "fat", "carbs", "fiber", "iron", "vitc", "calcium"]


def _safe_float(val: str) -> float:
    if not val or val.strip() in ("", "-", "Tr", "tr", "NA", "na"):
        return 0.0
    cleaned = re.sub(r"[^\d.\-]", "", val.strip())
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0


def load_tkpi(path: str = TKPI_PATH, db_prices: Optional[dict] = None) -> list[dict]:
    """
    Load TKPI CSV and return food items ready for LP optimization.

    db_prices: optional dict {food_code: price_per_100g} from food_prices table.
               When provided, overrides the CSV price column (which starts at 0).
               Items with price=0 after overlay are excluded from optimization.
    """
    items = []
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = (row.get("KODE") or "").strip()
            name = (row.get("NAMA BAHAN") or "").strip()
            if not code or not name:
                continue

            item = {"code": code, "name": name}
            for csv_col, key in COL_MAP.items():
                if key in ("code", "name"):
                    continue
                item[key] = _safe_float(row.get(csv_col, ""))

            # Overlay DB price (per 100g) if available
            if db_prices and code in db_prices:
                item["price"] = float(db_prices[code])

            # Skip items with no energy data
            if item["energy"] <= 0:
                continue
            # Skip items with no price (can't optimize cost without price)
            if item["price"] <= 0:
                continue

            item["category"] = categorize_food(code, name)
            items.append(item)
    return items


# ── Food categorization ──────────────────────────────────────────────────────

_STAPLE_KW = [
    "beras", "nasi", "mie ", "mi ", "roti", "jagung", "singkong",
    "kentang", "ubi", "sagu", "tepung beras", "havermut", "oat",
]
_ANIMAL_KW = [
    "ayam", "ikan", "telur", "daging", "udang", "cumi", "kepiting",
    "sapi", "kambing", "bebek", "itik", "lele", "tongkol", "tuna",
    "bandeng", "patin", "nila", "gurame", "sardine", "teri",
    "hati ayam", "hati sapi",
]
_PLANT_KW = [
    "tempe", "tahu", "kacang", "kedelai", "oncom", "edamame",
]
_FRUIT_KW = [
    "pisang", "jeruk", "pepaya", "mangga", "apel", "semangka",
    "melon", "anggur", "nanas", "jambu", "alpukat", "salak",
    "rambutan", "durian", "kelengkeng", "manggis", "sawo",
]
_VEGETABLE_KW = [
    "bayam", "kangkung", "wortel", "buncis", "kol", "kubis",
    "sawi", "brokoli", "terong", "labu", "tomat", "timun",
    "selada", "daun", "pare", "gambas", "oyong", "rebung",
    "tauge", "jagung muda", "kecambah", "nangka muda",
    "jantung pisang",
]


def categorize_food(code: str, name: str) -> str:
    lower = name.lower()
    for kw in _STAPLE_KW:
        if kw in lower:
            return "staple"
    for kw in _ANIMAL_KW:
        if kw in lower:
            return "animal"
    for kw in _PLANT_KW:
        if kw in lower:
            return "plant"
    for kw in _FRUIT_KW:
        if kw in lower:
            return "fruit"
    for kw in _VEGETABLE_KW:
        if kw in lower:
            return "vegetable"
    return "other"


# ── Portion limits (grams per serving) ───────────────────────────────────────

PORTION_LIMITS = {
    "staple":    (100, 250),
    "animal":    (30,  120),
    "plant":     (25,  100),
    "vegetable": (30,  200),
    "fruit":     (30,  150),
    "other":     (0,   100),
}

# ── Default AKG constraints (lunch ~30-35% of daily for SD 7-12) ─────────────

DEFAULT_CONSTRAINTS = {
    "min_energy":  600,   # kcal
    "min_protein": 15,    # g
    "max_fat":     25,    # g
    "min_carbs":   80,    # g
    "min_fiber":   4,     # g
    "min_iron":    3,     # mg
    "min_vitc":    15,    # mg
}

# ── AKG presets per age group (lunch ~30% of daily AKG) ──────────────────────
# Source: Permenkes 28/2019 — Angka Kecukupan Gizi
AKG_PRESETS = {
    "TK (4-6 tahun)": {
        "min_energy":  405,   # 30% of 1350 kcal
        "min_protein": 7,     # 30% of 25g
        "max_fat":     18,    # 30% of 62g (total fat)
        "min_carbs":   65,    # 30% of 215g
        "min_fiber":   6,     # 30% of 20g
        "min_iron":    3,     # 30% of 10mg
        "min_vitc":    12,    # 30% of 40mg
    },
    "SD (7-9 tahun)": {
        "min_energy":  500,   # 30% of 1650 kcal
        "min_protein": 12,    # 30% of 40g
        "max_fat":     20,    # 30% of 65g
        "min_carbs":   75,    # 30% of 250g
        "min_fiber":   7,     # 30% of 23g
        "min_iron":    3,     # 30% of 10mg
        "min_vitc":    15,    # 30% of 50mg
    },
    "SD (10-12 tahun)": {
        "min_energy":  600,   # 30% of 2000 kcal
        "min_protein": 15,    # 30% of 50g
        "max_fat":     25,    # 30% of 80g
        "min_carbs":   80,    # 30% of 300g (approx)
        "min_fiber":   8,     # 30% of 28g
        "min_iron":    3,     # 30% of 13mg
        "min_vitc":    15,    # 30% of 50mg
    },
    "SMP (13-15 tahun)": {
        "min_energy":  720,   # 30% of 2400 kcal
        "min_protein": 21,    # 30% of 70g
        "max_fat":     25,    # 30% of 80g
        "min_carbs":   105,   # 30% of 350g
        "min_fiber":   10,    # 30% of 34g
        "min_iron":    4,     # 30% of 15mg (avg L/P)
        "min_vitc":    20,    # 30% of 75mg
    },
    "SMA (16-18 tahun)": {
        "min_energy":  750,   # 30% of 2500 kcal (avg L/P)
        "min_protein": 20,    # 30% of 65g (avg)
        "max_fat":     25,    # 30% of 85g
        "min_carbs":   120,   # 30% of 400g
        "min_fiber":   11,    # 30% of 37g
        "min_iron":    5,     # 30% of 17mg (avg)
        "min_vitc":    25,    # 30% of 90mg
    },
}

DAY_LABELS = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]


# ── LP solver ────────────────────────────────────────────────────────────────

def optimize_day(
    foods: list[dict],
    constraints: dict,
    excluded_codes: set[str] | None = None,
) -> list[dict] | None:
    """Solve one day's meal using linear programming. Returns list of items or None if infeasible."""
    excluded = excluded_codes or set()
    pool = [f for f in foods if f["code"] not in excluded]

    if not pool:
        return None

    prob = LpProblem("meal", LpMinimize)

    # Decision variables: grams of each food
    x = {}
    for f in pool:
        cat = f["category"]
        lo, hi = PORTION_LIMITS.get(cat, (0, 100))
        x[f["code"]] = LpVariable(f"x_{f['code']}", lowBound=0, upBound=hi)

    # Objective: minimize total cost per serving
    prob += lpSum(f["price"] / 100 * x[f["code"]] for f in pool)

    # Nutritional constraints
    c = constraints
    prob += lpSum(f["energy"] / 100 * x[f["code"]] for f in pool) >= c["min_energy"]
    prob += lpSum(f["protein"] / 100 * x[f["code"]] for f in pool) >= c["min_protein"]
    prob += lpSum(f["fat"] / 100 * x[f["code"]] for f in pool) <= c["max_fat"]
    prob += lpSum(f["carbs"] / 100 * x[f["code"]] for f in pool) >= c["min_carbs"]
    if c.get("min_fiber", 0) > 0:
        prob += lpSum(f["fiber"] / 100 * x[f["code"]] for f in pool) >= c["min_fiber"]
    if c.get("min_iron", 0) > 0:
        prob += lpSum(f["iron"] / 100 * x[f["code"]] for f in pool) >= c["min_iron"]
    if c.get("min_vitc", 0) > 0:
        prob += lpSum(f["vitc"] / 100 * x[f["code"]] for f in pool) >= c["min_vitc"]
    if c.get("max_cost", 0) > 0:
        prob += lpSum(f["price"] / 100 * x[f["code"]] for f in pool) <= c["max_cost"]

    # Must include at least one item from key categories
    for cat in ("staple", "animal", "vegetable"):
        cat_foods = [f for f in pool if f["category"] == cat]
        if cat_foods:
            lo = PORTION_LIMITS[cat][0]
            prob += lpSum(x[f["code"]] for f in cat_foods) >= lo

    # Solve
    prob.solve(PULP_CBC_CMD(msg=0))

    if prob.status != LpStatusOptimal:
        return None

    # Extract results
    result = []
    for f in pool:
        grams = value(x[f["code"]])
        if grams is not None and grams > 0.5:
            grams = round(grams, 1)
            cost = round(f["price"] / 100 * grams, 1)
            nutrition = {k: round(f[k] / 100 * grams, 2) for k in NUTRIENT_KEYS}
            result.append({
                "code": f["code"],
                "name": f["name"],
                "category": f["category"],
                "grams": grams,
                "cost": cost,
                "nutrition": nutrition,
            })

    # Sort by category order
    cat_order = {"staple": 0, "animal": 1, "plant": 2, "vegetable": 3, "fruit": 4, "other": 5}
    result.sort(key=lambda r: cat_order.get(r["category"], 9))
    return result


def optimize_week(
    foods: list[dict],
    num_days: int = 5,
    constraints: Optional[dict] = None,
    excluded_foods: Optional[list[str]] = None,
) -> list[dict]:
    """Generate a full week of optimized menus with variety."""
    c = {**DEFAULT_CONSTRAINTS, **(constraints or {})}
    global_excluded = set(excluded_foods or [])

    week = []
    used_animal = set()
    used_vegetable = set()

    for day_idx in range(num_days):
        # Exclude animal proteins and vegetables used on previous days
        day_excluded = global_excluded | used_animal | used_vegetable

        result = optimize_day(foods, c, day_excluded)

        if result is None:
            # Relax variety constraints if infeasible
            result = optimize_day(foods, c, global_excluded)

        if result is None:
            week.append({"day": day_idx + 1, "label": DAY_LABELS[day_idx], "items": [], "feasible": False})
            continue

        # Track used items for variety
        for item in result:
            if item["category"] == "animal":
                used_animal.add(item["code"])
            elif item["category"] == "vegetable":
                used_vegetable.add(item["code"])

        # Aggregate nutrition and cost
        total_cost = sum(item["cost"] for item in result)
        total_nutrition = {}
        for key in NUTRIENT_KEYS:
            total_nutrition[key] = round(sum(item["nutrition"][key] for item in result), 1)

        week.append({
            "day": day_idx + 1,
            "label": DAY_LABELS[day_idx],
            "items": result,
            "nutrition": total_nutrition,
            "cost_per_serving": round(total_cost),
            "feasible": True,
        })

    return week
