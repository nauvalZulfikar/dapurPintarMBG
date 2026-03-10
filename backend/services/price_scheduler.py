# backend/services/price_scheduler.py
"""
Daily price scraper scheduler.

Runs once a day (default: 02:00 WIB) and scrapes market prices from Sayurbox
for all food items in data/tkpi.csv, then saves results to the food_prices table.

Integrated into FastAPI via lifespan in backend/app.py using APScheduler.
"""
import csv
import logging
import os
import re
from datetime import datetime

logger = logging.getLogger(__name__)

TKPI_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "tkpi.csv",
)

# ── Keyword generation ────────────────────────────────────────────────────────

# Words to strip from food names to make better search keywords
_STRIP_WORDS = {
    "segar", "kering", "rebus", "goreng", "kukus", "panggang", "bakar",
    "mentah", "matang", "olahan", "produk", "kaleng", "beku",
    "tanpa", "dengan", "dan", "atau", "dari",
}

# Short name prefixes that are good search keywords on their own
_SHORT_OK = {"mie", "mi", "tahu", "tempe", "nasi", "roti"}


def _food_name_to_keyword(name: str) -> str:
    """
    Convert a TKPI food name to a concise Sayurbox search keyword.

    Examples:
        'Ayam broiler, dada, tanpa kulit, segar' → 'ayam broiler dada'
        'Beras giling, putih, mentah' → 'beras putih'
        'Bayam, segar' → 'bayam'
    """
    # Remove parenthetical content and trailing notes
    name = re.sub(r"\(.*?\)", "", name)
    # Split on comma — take first 2 meaningful parts
    parts = [p.strip().lower() for p in name.split(",")]
    parts = [p for p in parts if p and p not in _STRIP_WORDS]

    # Take up to 2 parts, max 3 words total
    keyword_parts = []
    word_count = 0
    for part in parts[:2]:
        words = [w for w in part.split() if w not in _STRIP_WORDS]
        for w in words:
            if word_count >= 3:
                break
            keyword_parts.append(w)
            word_count += 1

    return " ".join(keyword_parts) if keyword_parts else name.split(",")[0].strip().lower()


def load_tkpi_items_for_scraping() -> list[dict]:
    """Load all food items from tkpi.csv for price scraping."""
    items = []
    if not os.path.isfile(TKPI_PATH):
        logger.error("tkpi.csv not found at %s", TKPI_PATH)
        return items

    with open(TKPI_PATH, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            code = (row.get("KODE") or "").strip()
            name = (row.get("NAMA BAHAN") or "").strip()
            if not code or not name:
                continue
            keyword = _food_name_to_keyword(name)
            items.append({"code": code, "name": name, "keyword": keyword})
    return items


# ── Scrape job ────────────────────────────────────────────────────────────────

def run_price_scrape(batch_size: int = 50, max_items: int = 0) -> dict:
    """
    Scrape prices for all TKPI items and save to food_prices table.

    Args:
        batch_size: items per Playwright subprocess call (processed sequentially)
        max_items: cap total items (0 = all). Useful for testing.

    Returns:
        dict with counts: total, scraped, failed
    """
    from backend.services.price_scraper import get_price_for_keyword
    from backend.core.database import db_upsert_food_price

    items = load_tkpi_items_for_scraping()
    if max_items > 0:
        items = items[:max_items]

    total = len(items)
    scraped = 0
    failed = 0
    already_done: set[str] = set()  # deduplicate same keyword

    logger.info("Price scrape started: %d items", total)

    for i, item in enumerate(items):
        kw = item["keyword"]

        # Skip duplicate keywords (same food type, different preparation)
        # but still save the price under the specific code
        try:
            price = get_price_for_keyword(kw)
            if price and price > 0:
                db_upsert_food_price(
                    food_code=item["code"],
                    food_name=item["name"],
                    price_per_100g=int(price),
                    source="sayurbox",
                )
                scraped += 1
                logger.debug("[%d/%d] %s → Rp %d /100g", i + 1, total, item["name"][:40], price)
            else:
                failed += 1
                logger.debug("[%d/%d] %s → not found", i + 1, total, item["name"][:40])
        except Exception as e:
            failed += 1
            logger.warning("Scrape error for %s (%s): %s", item["code"], kw, e)

    logger.info(
        "Price scrape done: %d/%d scraped, %d failed",
        scraped, total, failed,
    )
    return {"total": total, "scraped": scraped, "failed": failed, "at": datetime.now().isoformat()}


# ── Scheduler setup ───────────────────────────────────────────────────────────

def start_scheduler():
    """
    Start APScheduler with a daily job at 02:00 Asia/Jakarta.
    Returns the scheduler instance (keep a reference to prevent GC).
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.warning(
            "APScheduler not installed. Daily price scraping disabled. "
            "Run: pip install apscheduler"
        )
        return None

    sched = BackgroundScheduler(timezone="Asia/Jakarta")

    sched.add_job(
        run_price_scrape,
        trigger=CronTrigger(hour=2, minute=0, timezone="Asia/Jakarta"),
        id="daily_price_scrape",
        replace_existing=True,
        misfire_grace_time=3600,  # run even if missed by up to 1h
        kwargs={"batch_size": 50},
    )

    sched.start()
    logger.info("Price scrape scheduler started — daily at 02:00 WIB")
    return sched


def stop_scheduler(sched) -> None:
    if sched and sched.running:
        sched.shutdown(wait=False)
        logger.info("Price scrape scheduler stopped")
