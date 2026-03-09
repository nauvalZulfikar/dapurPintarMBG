# backend/services/price_scraper.py
"""
Price scraper for Indonesian grocery platforms.
Fetches ingredient prices from Happyfresh, Segari, Sayurbox.
For internal MBG kitchen menu optimizer use only.

Usage:
    from backend.services.price_scraper import get_prices
    prices = get_prices(["ayam", "beras", "tempe"])
    # -> {"ayam": 35000, "beras": 12000, "tempe": 8000}  (per 100g, IDR)
"""
import re
import time
import json
import logging
import difflib
from typing import Optional
from urllib.parse import quote_plus

import requests

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
}

# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _parse_price(text: str) -> Optional[float]:
    """Extract numeric price from strings like 'Rp 12.500' or '12500'."""
    cleaned = re.sub(r"[^\d]", "", text)
    return float(cleaned) if cleaned else None


def _normalize_to_100g(price: float, weight_g: float) -> float:
    """Convert price/weight to price per 100 g."""
    return (price / weight_g) * 100 if weight_g > 0 else price


def _best_match(query: str, candidates: list[str], threshold: float = 0.5) -> Optional[str]:
    """Return the best fuzzy-matching candidate or None."""
    q = query.lower()
    matches = difflib.get_close_matches(q, [c.lower() for c in candidates], n=1, cutoff=threshold)
    if not matches:
        return None
    idx = [c.lower() for c in candidates].index(matches[0])
    return candidates[idx]


# ------------------------------------------------------------------ #
# Happyfresh  (REST API — uses internal search endpoint)
# ------------------------------------------------------------------ #

def _scrape_happyfresh(keyword: str) -> Optional[float]:
    """
    Happyfresh has a JSON search endpoint used by their SPA.
    Returns price per 100 g (IDR) or None.
    """
    try:
        url = (
            f"https://www.happyfresh.id/api/v3/search?"
            f"query={quote_plus(keyword)}&page=1&per_page=5"
        )
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            logger.debug("Happyfresh %s → HTTP %s", keyword, r.status_code)
            return None
        data = r.json()

        products = data.get("data", {}).get("products", [])
        if not products:
            return None

        # pick first product whose name roughly matches
        names = [p.get("name", "") for p in products]
        best = _best_match(keyword, names)
        if not best:
            return None
        prod = products[[p["name"] for p in products].index(best)]

        price = _parse_price(str(prod.get("price", 0)))
        weight_text = prod.get("unit_of_measure", "100g")
        weight_g = _extract_grams(weight_text)
        if price and weight_g:
            return _normalize_to_100g(price, weight_g)
    except Exception as e:
        logger.debug("Happyfresh error for '%s': %s", keyword, e)
    return None


# ------------------------------------------------------------------ #
# Segari  (public search endpoint)
# ------------------------------------------------------------------ #

def _scrape_segari(keyword: str) -> Optional[float]:
    """
    Segari exposes a product search endpoint.
    Returns price per 100 g (IDR) or None.
    """
    try:
        url = (
            f"https://segari.id/api/v1/product/search?"
            f"keyword={quote_plus(keyword)}&limit=5"
        )
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            logger.debug("Segari %s → HTTP %s", keyword, r.status_code)
            return None
        data = r.json()

        products = (
            data.get("data", {}).get("products", [])
            or data.get("data", [])
        )
        if not products:
            return None

        names = [p.get("name", "") for p in products]
        best = _best_match(keyword, names)
        if not best:
            return None
        prod = products[[p.get("name", "") for p in products].index(best)]

        price = _parse_price(str(prod.get("price", prod.get("sale_price", 0))))
        weight_g = _extract_grams(
            prod.get("unit", prod.get("weight_unit", "100g"))
        )
        if price and weight_g:
            return _normalize_to_100g(price, weight_g)
    except Exception as e:
        logger.debug("Segari error for '%s': %s", keyword, e)
    return None


# ------------------------------------------------------------------ #
# Sayurbox  (search API)
# ------------------------------------------------------------------ #

def _scrape_sayurbox(keyword: str) -> Optional[float]:
    """
    Sayurbox public search endpoint.
    Returns price per 100 g (IDR) or None.
    """
    try:
        url = (
            f"https://www.sayurbox.com/api/products/search?"
            f"q={quote_plus(keyword)}&limit=5"
        )
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            logger.debug("Sayurbox %s → HTTP %s", keyword, r.status_code)
            return None
        data = r.json()

        products = data.get("data", data.get("products", []))
        if isinstance(data, list):
            products = data

        if not products:
            return None

        names = [p.get("name", p.get("productName", "")) for p in products]
        best = _best_match(keyword, names)
        if not best:
            return None
        idx = [n.lower() for n in names].index(best.lower())
        prod = products[idx]

        price = _parse_price(
            str(prod.get("price", prod.get("finalPrice", prod.get("sellingPrice", 0))))
        )
        weight_g = _extract_grams(
            prod.get("unit", prod.get("weight", prod.get("packagingUnit", "100g")))
        )
        if price and weight_g:
            return _normalize_to_100g(price, weight_g)
    except Exception as e:
        logger.debug("Sayurbox error for '%s': %s", keyword, e)
    return None


# ------------------------------------------------------------------ #
# Weight extraction helper
# ------------------------------------------------------------------ #

def _extract_grams(text: str) -> Optional[float]:
    """
    Parse weight strings like '500 gr', '1 kg', '250g', '1 liter (approx 1000g)'.
    Returns grams as float, defaults to 100 if unrecognised.
    """
    if not text:
        return 100.0
    text = str(text).lower().replace(",", ".")
    # kg
    m = re.search(r"(\d+\.?\d*)\s*kg", text)
    if m:
        return float(m.group(1)) * 1000
    # g / gr / gram
    m = re.search(r"(\d+\.?\d*)\s*g(?:r(?:am)?)?", text)
    if m:
        return float(m.group(1))
    # ml / liter (assume 1ml ≈ 1g for liquids — rough)
    m = re.search(r"(\d+\.?\d*)\s*(?:ml|liter|litre|l\b)", text)
    if m:
        val = float(m.group(1))
        return val * 1000 if val < 100 else val
    # bare number → assume grams
    m = re.search(r"(\d+\.?\d*)", text)
    if m:
        return float(m.group(1))
    return 100.0


# ------------------------------------------------------------------ #
# Public interface
# ------------------------------------------------------------------ #

def get_price_for_keyword(keyword: str, delay: float = 0.5) -> Optional[float]:
    """
    Try all three sources. Return average of those that succeed.
    Returns price per 100 g (IDR) or None if all fail.
    """
    results = []

    for scraper_fn in [_scrape_happyfresh, _scrape_segari, _scrape_sayurbox]:
        price = scraper_fn(keyword)
        if price and price > 0:
            results.append(price)
        time.sleep(delay)

    if not results:
        return None
    return sum(results) / len(results)


def get_prices(keywords: list[str], delay: float = 0.5) -> dict[str, Optional[float]]:
    """
    Fetch prices for a list of ingredient keywords.
    Returns dict: keyword -> price_per_100g_idr (or None if not found).

    Example:
        get_prices(["ayam broiler", "beras putih", "tempe"])
        # -> {"ayam broiler": 3200.0, "beras putih": 1250.0, "tempe": 850.0}
    """
    out = {}
    for kw in keywords:
        price = get_price_for_keyword(kw, delay=delay)
        out[kw] = price
        logger.info("Price [%s] = %s IDR/100g", kw, f"Rp {price:.0f}" if price else "not found")
    return out


# ------------------------------------------------------------------ #
# CLI test
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    test_keywords = sys.argv[1:] if len(sys.argv) > 1 else [
        "ayam broiler",
        "beras putih",
        "tempe",
        "tahu putih",
        "kangkung",
        "telur ayam",
        "pisang ambon",
        "wortel",
    ]
    print("Fetching prices (this may take ~30s)...\n")
    prices = get_prices(test_keywords)
    print("\n=== RESULTS ===")
    for kw, p in prices.items():
        if p:
            print(f"  {kw:<25} Rp {p:>8.0f} / 100g")
        else:
            print(f"  {kw:<25} — not found")
