#!/usr/bin/env python3
"""
syncer.py
---------
Background sync worker. Runs as a daemon thread inside the scanner process.

Every 60 seconds:
  1. Push unsynced rows from local_scan_queue -> Supabase
     - Processing -> UPDATE items SET processing=True + timestamps
     - Packing    -> UPDATE trays SET packing=True + timestamps
     - Delivery   -> UPDATE trays SET delivery=True + timestamps
  2. Push unsynced scan errors -> Supabase scan_errors
  3. Delete successfully synced rows from local SQLite
  4. If Supabase unreachable, keep local and retry next cycle
"""

import time
import threading
from datetime import datetime, date

from sqlalchemy import select

from backend.core.database import (
    local_engine,
    remote_engine,
    local_scan_queue,
    local_scan_errors,
    remote_items,
    remote_trays,
    remote_scan_errors,
)

SYNC_INTERVAL = 60  # seconds


def _sync_scans():
    with local_engine.connect() as local:
        rows = local.execute(
            select(local_scan_queue).where(local_scan_queue.c.synced == 0)
        ).fetchall()

    if not rows:
        return

    with remote_engine.begin() as remote:
        for row in rows:
            code  = row.code
            step  = row.step
            now   = datetime.now()
            today = date.today()

            if step == "Processing":
                remote.execute(
                    remote_items.update()
                    .where(remote_items.c.id == code)
                    .values(
                        processing=True,
                        created_at_processing=now,
                        created_date_processing=today,
                    )
                )

            elif step == "Packing":
                existing = remote.execute(
                    select(remote_trays.c.tray_id)
                    .where(remote_trays.c.tray_id == code)
                ).first()

                if existing:
                    remote.execute(
                        remote_trays.update()
                        .where(remote_trays.c.tray_id == code)
                        .values(
                            packing=True,
                            created_at_packing=now,
                            created_date_packing=today,
                        )
                    )
                else:
                    remote.execute(
                        remote_trays.insert().values(
                            tray_id=code,
                            packing=True,
                            created_at_packing=now,
                            created_date_packing=today,
                        )
                    )

            elif step == "Delivery":
                remote.execute(
                    remote_trays.update()
                    .where(remote_trays.c.tray_id == code)
                    .values(
                        delivery=True,
                        created_at_delivery=now,
                        created_date_delivery=today,
                    )
                )

    synced_ids = [row.id for row in rows]
    with local_engine.begin() as local:
        local.execute(
            local_scan_queue.delete()
            .where(local_scan_queue.c.id.in_(synced_ids))
        )

    print(f"[SYNC] Done. {len(synced_ids)} scan(s) synced to Supabase.", flush=True)


def _sync_errors():
    with local_engine.connect() as local:
        rows = local.execute(
            select(local_scan_errors).where(local_scan_errors.c.synced == 0)
        ).fetchall()

    if not rows:
        return

    with remote_engine.begin() as remote:
        for row in rows:
            remote.execute(
                remote_scan_errors.insert().values(
                    code=row.code,
                    step=row.step,
                    created_at=row.created_at,
                    reason=row.reason,
                )
            )

    synced_ids = [row.id for row in rows]
    with local_engine.begin() as local:
        local.execute(
            local_scan_errors.delete()
            .where(local_scan_errors.c.id.in_(synced_ids))
        )

    print(f"[SYNC] Done. {len(synced_ids)} error(s) synced to Supabase.", flush=True)


def _sync_cycle():
    if not remote_engine:
        print("[SYNC] No remote engine (DATABASE_URL not set). Skipping.", flush=True)
        return
    try:
        _sync_scans()
        _sync_errors()
    except Exception as e:
        print(f"[SYNC] Failed, will retry in {SYNC_INTERVAL}s: {e}", flush=True)


def _sync_loop():
    print(f"[SYNC] Background sync thread started (every {SYNC_INTERVAL}s).", flush=True)
    while True:
        time.sleep(SYNC_INTERVAL)
        _sync_cycle()


def start_sync_thread():
    thread = threading.Thread(target=_sync_loop, daemon=True, name="supabase-syncer")
    thread.start()
    return thread