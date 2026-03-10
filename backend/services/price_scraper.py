# backend/services/price_scraper.py
"""
Price scraper for Indonesian grocery market prices.
Uses Playwright headless browser to scrape Sayurbox product search results.

Sayurbox is the only reliably scrapable source — Happyfresh requires city
context, Segari blocks bots, Tokopedia/Shopee require auth tokens.

Usage:
    from backend.services.price_scraper import get_prices
    prices = get_prices(["ayam", "beras", "tempe"])
    # -> {"ayam": 2800.0, "beras": 1250.0, "tempe": 850.0}  (per 100g, IDR)

Requirements:
    pip install playwright
    playwright install chromium
"""
import re
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _parse_price(text: str) -> Optional[float]:
    """Extract numeric IDR value from strings like 'Rp18.900' or '18900'."""
    cleaned = re.sub(r"[^\d]", "", str(text))
    return float(cleaned) if cleaned else None


def _normalize_to_100g(price: float, weight_g: float) -> float:
    return (price / weight_g) * 100 if weight_g > 0 else price


def _extract_grams(text: str) -> Optional[float]:
    """
    Parse weight from strings like '500 gr', '1 kg', '250g'.
    Returns None if the string doesn't contain a recognisable weight unit
    (so the caller can fall back to _guess_weight_g).
    """
    if not text:
        return None
    t = str(text).lower().replace(",", ".")
    # Must contain a weight unit to be trusted
    m = re.search(r"(\d+\.?\d*)\s*kg", t)
    if m:
        return float(m.group(1)) * 1000
    m = re.search(r"(\d+\.?\d*)\s*g(?:r(?:am)?)?", t)
    if m:
        val = float(m.group(1))
        return val if val >= 10 else None   # ignore tiny values like "3g"
    m = re.search(r"(\d+\.?\d*)\s*(?:ml|liter|litre|l\b)", t)
    if m:
        val = float(m.group(1))
        return val * 1000 if val < 10 else val
    return None   # no weight unit found → caller uses typical weight


def _best_match_score(query: str, candidates: list[str]) -> tuple[Optional[str], float]:
    """Return best fuzzy match and its similarity score."""
    if not candidates:
        return None, 0.0
    q = query.lower()
    scored = [(c, difflib.SequenceMatcher(None, q, c.lower()).ratio()) for c in candidates]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[0]


# ------------------------------------------------------------------ #
# Sayurbox — Playwright DOM scraper
# ------------------------------------------------------------------ #

def _scrape_sayurbox_playwright(keyword: str) -> list[dict]:
    """
    Launch headless Chromium in a subprocess to avoid asyncio/IocpProactor
    conflicts when called from within a FastAPI/asyncio process on Windows.
    Returns list of {name, price, weight_text} dicts.
    """
    import json
    import subprocess
    import sys

    # Mini script that runs playwright in a clean process and prints JSON
    script = r"""
import sys, re, json
from playwright.sync_api import sync_playwright

keyword = sys.argv[1]
results = []
try:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        url = f"https://www.sayurbox.com/search?q={keyword.replace(' ', '+')}"
        page.goto(url, timeout=30000, wait_until="commit")
        page.wait_for_selector("text=Rp", timeout=20000)
        page.wait_for_timeout(500)
        content = page.content()
        browser.close()

        tokens = re.findall(r'font-family: Geist[^;]+;">([^<]{1,200})</div>', content)
        i = 0
        while i < len(tokens):
            tok = tokens[i].strip()
            if tok.startswith("Rp"):
                raw = re.sub(r"[^\d]", "", tok)
                price = float(raw) if raw else 0
                name = tokens[i + 1].strip() if i + 1 < len(tokens) else ""
                weight_text = tokens[i + 2].strip() if i + 2 < len(tokens) else ""
                if price > 500 and name and not name.startswith("Rp"):
                    results.append({"name": name, "price": price, "weight_text": weight_text})
                i += 3
            else:
                i += 1
except Exception as e:
    print(json.dumps({"__error__": str(e)}), file=sys.stderr)

print(json.dumps(results))
"""
    try:
        import os
        proc = subprocess.run(
            [sys.executable, "-c", script, keyword],
            capture_output=True, text=True, timeout=60,
            env=os.environ.copy(),
        )
        if proc.stderr.strip():
            logger.warning("Sayurbox subprocess stderr for '%s': %s", keyword, proc.stderr.strip()[:500])
        if proc.returncode != 0:
            logger.warning("Sayurbox subprocess exit %d for '%s': %s", proc.returncode, keyword, proc.stderr.strip()[:300])
            return []
        if proc.stdout.strip():
            all_results = json.loads(proc.stdout.strip())
            kw_lower = keyword.lower()
            matched = [r for r in all_results if kw_lower in r["name"].lower()]
            return matched if matched else all_results[:5]
    except Exception as e:
        logger.warning("Sayurbox subprocess error for '%s': %s", keyword, e)

    return []


def _parse_sayurbox_html(content: str, keyword: str) -> list[dict]:
    """
    Parse Sayurbox search result HTML.

    Sayurbox uses React Native Web with inline styles (Geist font).
    Each product card renders as consecutive divs with text:
        Rp<price>  →  <product name>  →  <weight text>

    We extract all Geist-font text nodes, then find consecutive
    (price, name, weight) triples.
    """
    # Extract all text content from Geist-font divs (product card fields)
    tokens = re.findall(r'font-family: Geist[^;]+;">([^<]{1,200})</div>', content)

    results = []
    i = 0
    while i < len(tokens):
        tok = tokens[i].strip()
        # Price token: starts with "Rp"
        if tok.startswith("Rp"):
            price = _parse_price(tok)
            name = tokens[i + 1].strip() if i + 1 < len(tokens) else ""
            weight_text = tokens[i + 2].strip() if i + 2 < len(tokens) else ""
            # Validate: name should not start with Rp (another price)
            if price and price > 500 and name and not name.startswith("Rp"):
                results.append({"name": name, "price": price, "weight_text": weight_text})
            i += 3
        else:
            i += 1

    # Filter to items whose name contains the keyword (case-insensitive)
    kw_lower = keyword.lower()
    matched = [r for r in results if kw_lower in r["name"].lower()]

    # Fall back to all results if no exact match (e.g. brand names)
    return matched if matched else results[:5]


# ------------------------------------------------------------------ #
# Price-per-100g estimator
# ------------------------------------------------------------------ #

# Typical package sizes for Indonesian grocery items (grams)
# Used when no weight info is available in search results
TYPICAL_WEIGHTS = {
    "ayam": 500,
    "ikan": 500,
    "daging": 500,
    "sapi": 500,
    "udang": 500,
    "telur": 600,   # 10-butir box
    "tempe": 300,
    "tahu": 400,
    "kangkung": 250,
    "bayam": 250,
    "wortel": 500,
    "tomat": 500,
    "kentang": 500,
    "beras": 5000,
    "mie": 500,
    "tepung": 1000,
    "gula": 1000,
    "minyak": 1000,
    "kacang": 500,
    "pisang": 1000,
    "jeruk": 1000,
    "apel": 1000,
}


def _guess_weight_g(keyword: str) -> float:
    """Guess typical package size based on keyword."""
    kw_lower = keyword.lower()
    for k, w in TYPICAL_WEIGHTS.items():
        if k in kw_lower:
            return float(w)
    return 500.0  # default 500g


def _price_to_100g(price_idr: float, keyword: str, weight_text: str = "") -> float:
    """Convert a product price to IDR per 100g."""
    weight_g = _extract_grams(weight_text) if weight_text else None
    if weight_g is None:
        weight_g = _guess_weight_g(keyword)
    return _normalize_to_100g(price_idr, weight_g)


# ------------------------------------------------------------------ #
# Public interface
# ------------------------------------------------------------------ #

def get_price_for_keyword(keyword: str) -> Optional[float]:
    """
    Scrape Sayurbox for `keyword`, return average price per 100g (IDR).
    Returns None if not found.
    """
    products = _scrape_sayurbox_playwright(keyword)
    if not products:
        logger.info("Price [%s] = not found", keyword)
        return None

    prices_per_100g = [
        _price_to_100g(p["price"], keyword, p.get("weight_text", ""))
        for p in products
        if p.get("price") and p["price"] > 0
    ]
    if not prices_per_100g:
        return None

    avg = sum(prices_per_100g) / len(prices_per_100g)
    logger.info("Price [%s] = Rp %.0f /100g (from %d results)", keyword, avg, len(products))
    return avg


def get_prices(keywords: list[str], delay: float = 1.0) -> dict[str, Optional[float]]:
    """
    Fetch prices for a list of ingredient keywords.
    Returns dict: keyword -> price_per_100g_idr (or None if not found).

    Example:
        get_prices(["ayam broiler", "beras putih", "tempe"])
        # -> {"ayam broiler": 3200.0, "beras putih": 1250.0, "tempe": 850.0}

    Note: Each keyword takes ~5-8 seconds (Playwright page load).
          For 10 keywords expect ~60-80s total.
    """
    out = {}
    for kw in keywords:
        out[kw] = get_price_for_keyword(kw)
        if delay > 0:
            time.sleep(delay)
    return out


# ------------------------------------------------------------------ #
# CLI test
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    test_keywords = sys.argv[1:] if len(sys.argv) > 1 else [
        "ayam",
        "beras",
        "tempe",
        "kangkung",
        "telur",
    ]
    print(f"Fetching prices for: {test_keywords}")
    print("(Each keyword ~5-8s via Playwright headless browser)\n")
    prices = get_prices(test_keywords, delay=0.5)
    print("\n=== RESULTS ===")
    for kw, p in prices.items():
        if p:
            print(f"  {kw:<25} Rp {p:>8.0f} / 100g")
        else:
            print(f"  {kw:<25} — not found")
