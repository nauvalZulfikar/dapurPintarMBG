# DPMBG_Project/backend/core/database.py
import os
from datetime import date, datetime
from typing import Optional

from backend.utils.datetime_helpers import now_local_iso

from sqlalchemy import (
    create_engine, MetaData, Table, Column, Integer, String, Text,
    DateTime, Date, Boolean, Index, ForeignKey, UniqueConstraint,
    select, func, insert, update, NullPool
)
from dotenv import load_dotenv
load_dotenv()

# ============================================================
# ENGINES
# ============================================================
BASE_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_DB_URL  = f"sqlite:///{os.path.join(BASE_DIR, 'local_scans.db')}"
REMOTE_DB_URL = os.getenv("DATABASE_URL")

local_engine = create_engine(
    LOCAL_DB_URL,
    future=True,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False},
)

remote_engine = None
if REMOTE_DB_URL:
    remote_engine = create_engine(
        REMOTE_DB_URL, 
        future=True, 
        pool_pre_ping=True,
        pool_recycle=180,
        poolclass=NullPool
        )

# engine = remote if available, else local
engine = remote_engine if remote_engine else local_engine

# ============================================================
# LOCAL TABLES (SQLite on Android/Windows scanner)
# ============================================================
local_metadata = MetaData()

local_scan_queue = Table(
    "local_scan_queue", local_metadata,
    Column("id",         Integer, primary_key=True, autoincrement=True),
    Column("code",       Text, nullable=False),
    Column("step",       Text, nullable=False),    # "Processing" / "Packing" / "Delivery"
    Column("label",      Text, nullable=False),    # "processed" / "packed" / "delivered"
    Column("created_at", Text, nullable=False),
    Column("synced",     Integer, default=0),
)

local_scan_errors = Table(
    "local_scan_errors", local_metadata,
    Column("id",         Integer, primary_key=True, autoincrement=True),
    Column("code",       Text),
    Column("step",       Text, nullable=False),
    Column("created_at", Text, nullable=False),
    Column("reason",     Text, nullable=False),
    Column("synced",     Integer, default=0),
)

# ============================================================
# REMOTE TABLE REFERENCES (PostgreSQL)
# ============================================================
remote_metadata = MetaData()

# --- Organizations (top-level tenant: one entity / company / yayasan)
# Owns a set of kitchens and users. Keeps entities completely isolated when
# multiple parties share one deployment.
remote_organizations = Table(
    "organizations", remote_metadata,
    Column("id",         Integer, primary_key=True, autoincrement=True),
    Column("slug",       String(50), nullable=False, unique=True),   # e.g. "dpmbg"
    Column("name",       String(150), nullable=False),
    Column("active",     Boolean, server_default="true"),
    Column("created_at", DateTime, server_default=func.now()),
)

# --- Kitchens (second-level tenant, owned by an organization)
remote_kitchens = Table(
    "kitchens", remote_metadata,
    Column("id",              Integer, primary_key=True, autoincrement=True),
    Column("org_id",          Integer, ForeignKey("organizations.id"), nullable=True, index=True),
    Column("slug",            String(50), nullable=False),
    Column("name",            String(100), nullable=False),               # e.g. "DPMBG Paseh"
    Column("printer_name",    String(100), nullable=True),                # Windows printer device
    Column("printer_lang",    String(10), server_default="ZPL"),          # ZPL | TSPL
    Column("label_title",     String(100), server_default="MBG Kitchen"),
    Column("scanner_key",     String(64), nullable=False, unique=True),   # per-kitchen scanner auth
    Column("cloud_print_key", String(64), nullable=False, unique=True),   # per-kitchen printer agent auth
    Column("address",         Text, nullable=True),
    Column("timezone",        String(50), server_default="Asia/Jakarta"),
    Column("active",          Boolean, server_default="true"),
    Column("created_at",      DateTime, server_default=func.now()),
    UniqueConstraint("org_id", "slug", name="uq_kitchens_org_slug"),
)

# --- Ingredients (BHN-xxxxx)
remote_items = Table(
    "items", remote_metadata,
    Column("id",                      String, primary_key=True),
    Column("kitchen_id",              Integer, ForeignKey("kitchens.id"), nullable=True, index=True),
    Column("name",                    String),
    Column("weight_grams",            Integer),
    Column("unit",                    String),
    Column("reason",                  Text),
    Column("receiving",               Boolean, default=False),
    Column("created_at_receiving",    DateTime),
    Column("created_date_receiving",  Date),
    Column("processing",              Boolean, default=False),
    Column("created_at_processing",   DateTime),
    Column("created_date_processing", Date),
    # Phase 1 — supplier link (added via migration)
    Column("default_supplier_id",     Integer, nullable=True),
    # Phase 3 — Joint Inspection linkage (added via migration)
    Column("parent_po_line_id",       Integer, nullable=True),
    Column("inspection_line_id",      Integer, nullable=True),
    Column("storage_routing",         String(20), nullable=True),
)

# --- Trays (TRY-xxxxx)
remote_trays = Table(
    "trays", remote_metadata,
    Column("id",                    Integer, primary_key=True, autoincrement=True),
    Column("tray_id",               String, nullable=False),
    Column("kitchen_id",            Integer, ForeignKey("kitchens.id"), nullable=True, index=True),
    Column("reason",                Text),
    Column("packing",               Boolean, default=False),
    Column("created_at_packing",    DateTime),
    Column("created_date_packing",  Date),
    Column("delivery",              Boolean, default=False),
    Column("created_at_delivery",   DateTime),
    Column("created_date_delivery", Date),
    UniqueConstraint("tray_id", "kitchen_id", name="uq_trays_tray_kitchen"),
)

# --- Tray registry (used for Packing validation)
remote_tray_items = Table(
    "tray_items", remote_metadata,
    Column("id",         Integer, primary_key=True, autoincrement=True),
    Column("tray_id",    String, nullable=False),
    Column("kitchen_id", Integer, ForeignKey("kitchens.id"), nullable=True, index=True),
    UniqueConstraint("tray_id", "kitchen_id", name="uq_tray_items_tray_kitchen"),
)

# --- Scan errors
remote_scan_errors = Table(
    "scan_errors", remote_metadata,
    Column("id",         Integer, primary_key=True, autoincrement=True),
    Column("kitchen_id", Integer, ForeignKey("kitchens.id"), nullable=True, index=True),
    Column("code",       Text),
    Column("step",       Text, nullable=False),
    Column("created_at", Text, nullable=False),
    Column("reason",     Text, nullable=False),
)

# --- Print jobs
remote_print_jobs = Table(
    "print_jobs", remote_metadata,
    Column("id",         Integer, primary_key=True, autoincrement=True),
    Column("kitchen_id", Integer, ForeignKey("kitchens.id"), nullable=True, index=True),
    Column("tspl",       Text, nullable=False),
    Column("created_at", DateTime, server_default=func.now()),
    Column("printed",    Integer, server_default=func.cast(0, Integer)),
    Column("printed_at", DateTime, nullable=True),
)

# --- Users (JWT auth)
# Role hierarchy:
#   platform_admin — owns the platform, sees every organization
#   superadmin     — owns one organization, sees every kitchen in it
#   user           — per-kitchen role is stored in user_kitchens
remote_users = Table(
    "users", remote_metadata,
    Column("id",            Integer, primary_key=True, autoincrement=True),
    Column("org_id",        Integer, ForeignKey("organizations.id"), nullable=True, index=True),
    Column("username",      String(50), nullable=False),
    Column("password_hash", String(255), nullable=False),
    Column("role",          String(20), server_default="user"),
    Column("created_at",    DateTime, server_default=func.now()),
    UniqueConstraint("org_id", "username", name="uq_users_org_username"),
)

# --- User ↔ Kitchen (many-to-many with per-kitchen role)
remote_user_kitchens = Table(
    "user_kitchens", remote_metadata,
    Column("id",         Integer, primary_key=True, autoincrement=True),
    Column("user_id",    Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("kitchen_id", Integer, ForeignKey("kitchens.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("role",       String(20), server_default="staff"),   # "kitchen_admin" | "staff"
    Column("created_at", DateTime, server_default=func.now()),
    UniqueConstraint("user_id", "kitchen_id", name="uq_user_kitchen"),
)

# --- Food prices (scraped market prices per ingredient code)
# kitchen_id is NULL = global reference price; set to scope per kitchen if supplier differs.
remote_food_prices = Table(
    "food_prices", remote_metadata,
    Column("id",             Integer, primary_key=True, autoincrement=True),
    Column("kitchen_id",     Integer, ForeignKey("kitchens.id"), nullable=True, index=True),
    Column("food_code",      String(20), nullable=False),
    Column("food_name",      String(255), nullable=False),
    Column("price_per_100g", Integer, nullable=False, server_default="0"),
    Column("manual_price",   Integer, nullable=True),     # accountant override; wins over price_per_100g
    Column("manual_source",  String(255), nullable=True), # e.g. "invoice 2026-04" or supplier name
    Column("manual_set_by",  Integer, nullable=True),     # users.id of the accountant
    Column("manual_set_at",  DateTime, nullable=True),
    Column("source",         String(50), nullable=True),
    Column("scraped_at",     DateTime, nullable=True),
    Column("updated_at",     DateTime, server_default=func.now()),
    UniqueConstraint("food_code", "kitchen_id", name="uq_food_prices_code_kitchen"),
)

# --- Food nutrition overrides (ahli_gizi edits TKPI defaults per kitchen)
# Override blob is sparse — only fields explicitly set; loader merges over TKPI.
remote_food_nutrition_overrides = Table(
    "food_nutrition_overrides", remote_metadata,
    Column("id",         Integer, primary_key=True, autoincrement=True),
    Column("kitchen_id", Integer, ForeignKey("kitchens.id"), nullable=False, index=True),
    Column("food_code",  String(20), nullable=False),
    Column("overrides",  Text, nullable=False),   # JSON: {"energy":120,"protein":5.2,...}
    Column("updated_by", Integer, nullable=True),
    Column("updated_at", DateTime, server_default=func.now()),
    UniqueConstraint("kitchen_id", "food_code", name="uq_nutr_override_kitchen_code"),
)

# --- Price history log — written on every price change (scrape or manual override)
remote_food_prices_history = Table(
    "food_prices_history", remote_metadata,
    Column("id",            Integer, primary_key=True, autoincrement=True),
    Column("kitchen_id",    Integer, nullable=True, index=True),
    Column("food_code",     String(20), nullable=False, index=True),
    Column("price",         Integer, nullable=True),    # final effective price at time of change
    Column("manual_price",  Integer, nullable=True),    # manual portion if applicable
    Column("source",        String(50), nullable=True), # "scrape" | "manual" | "manual_clear"
    Column("changed_by",    Integer, nullable=True),
    Column("changed_at",    DateTime, server_default=func.now()),
)

# --- Saved menus (Phase 2 expansion: approval workflow + target date + status)
# Original payload blob kept; new fields drive the approval state machine and
# enable cycle-check (last 20-day BGN compliance) and forecast generation.
remote_saved_menus = Table(
    "saved_menus", remote_metadata,
    Column("id",                Integer, primary_key=True, autoincrement=True),
    Column("kitchen_id",        Integer, ForeignKey("kitchens.id"), nullable=False, index=True),
    Column("name",              String(150), nullable=False),
    Column("created_by",        Integer, ForeignKey("users.id"), nullable=False),
    Column("created_at",        DateTime, server_default=func.now()),
    Column("payload",           Text, nullable=False),    # JSON: {request: {...}, result: {...}} OR manual menu
    # Phase 2 — approval state machine
    Column("status",            String(20), server_default="draft", index=True),  # draft | pending_review | approved | locked | archived | rejected
    Column("source",            String(20), server_default="optimizer"),           # "optimizer" | "manual" — distinguishes 2A reverse-mode vs forward optimizer
    Column("target_date",       Date, nullable=True, index=True),                  # date this menu is planned to be served
    Column("target_school_id",  Integer, nullable=True, index=True),               # optional: scoped to a specific school
    Column("submitted_at",      DateTime, nullable=True),
    Column("submitted_by",      Integer, nullable=True),
    Column("approved_at",       DateTime, nullable=True),
    Column("approved_by",       Integer, nullable=True),
    Column("review_notes",      Text, nullable=True),
)
Index("ix_saved_menus_kitchen_created", remote_saved_menus.c.kitchen_id, remote_saved_menus.c.created_at)
Index("ix_saved_menus_status_date", remote_saved_menus.c.kitchen_id, remote_saved_menus.c.status, remote_saved_menus.c.target_date)

# --- Student menu requests (Phase 2A) — anak minta makan apa, ahli gizi confirm
remote_student_requests = Table(
    "student_requests", remote_metadata,
    Column("id",            Integer, primary_key=True, autoincrement=True),
    Column("kitchen_id",    Integer, ForeignKey("kitchens.id"), nullable=False, index=True),
    Column("school_id",     Integer, ForeignKey("schools.id", ondelete="SET NULL"), nullable=True, index=True),
    Column("kelas",         String(40), nullable=True),
    Column("student_name",  String(100), nullable=True),
    Column("request_text",  Text, nullable=False),
    Column("status",        String(20), server_default="open"),     # open | confirmed | rejected | fulfilled
    Column("ahli_gizi_notes", Text, nullable=True),
    Column("created_by",    Integer, ForeignKey("users.id"), nullable=True),
    Column("created_at",    DateTime, server_default=func.now()),
    Column("resolved_by",   Integer, nullable=True),
    Column("resolved_at",   DateTime, nullable=True),
)
Index("ix_student_requests_kitchen_status", remote_student_requests.c.kitchen_id, remote_student_requests.c.status)

# --- Audit log (sensitive operations: who did what, when)
# Used for compliance / incident investigation. Never deleted.
# Phase 0 expansion: + before_value, after_value, event_category for richer
# audit trails (BGN compliance requires "from what to what" for updates).
remote_audit_log = Table(
    "audit_log", remote_metadata,
    Column("id",             Integer, primary_key=True, autoincrement=True),
    Column("created_at",     DateTime, server_default=func.now(), index=True),
    Column("user_id",        Integer, nullable=True, index=True),     # null for anonymous (failed login)
    Column("kitchen_id",     Integer, nullable=True, index=True),
    Column("org_id",         Integer, nullable=True, index=True),
    Column("action",         String(80), nullable=False, index=True), # e.g. "user.create", "price.override", "login.fail"
    Column("event_category", String(30), nullable=True),  # auth | menu | receiving | production | distribution | finance | compliance | system  (composite index defined below)
    Column("target_type",    String(50), nullable=True),              # e.g. "user", "food_price", "kitchen"
    Column("target_id",      String(100), nullable=True),             # FK as string (FK type may vary)
    Column("before_value",   Text, nullable=True),                    # JSON snapshot before update/delete
    Column("after_value",    Text, nullable=True),                    # JSON snapshot after create/update
    Column("ip_address",     String(45), nullable=True),              # IPv4 or IPv6
    Column("details",        Text, nullable=True),                    # optional JSON blob (free-form context)
)
Index("ix_audit_log_action_created", remote_audit_log.c.action, remote_audit_log.c.created_at)
Index("ix_audit_log_event_category", remote_audit_log.c.event_category, remote_audit_log.c.created_at)

# --- Schools (Phase 1) — kitchen-scoped binaan list, replaces data/schools.json
# Backward-compat: keeps `legacy_school_id` (old JSON school_id as int) so the
# existing delivery allocation algorithm — which sorts by distance and counts
# students per school — works unchanged when wired against DB rows.
remote_schools = Table(
    "schools", remote_metadata,
    Column("id",                Integer, primary_key=True, autoincrement=True),
    Column("kitchen_id",        Integer, ForeignKey("kitchens.id"), nullable=False, index=True),
    Column("name",              String(150), nullable=False),
    Column("address",           Text, nullable=True),
    Column("level",             String(20), nullable=False),    # PAUD | TK | SD | SMP | SMA
    Column("age_group",         String(50), nullable=False),    # e.g. "SD (7-9 tahun)" — drives AKG preset
    Column("student_count",     Integer, nullable=False, server_default="0"),
    Column("distance",          Integer, nullable=False, server_default="0"),  # meters from kitchen
    Column("gps_lat",           String(20), nullable=True),
    Column("gps_long",          String(20), nullable=True),
    Column("contact",           String(100), nullable=True),
    Column("is_active",         Boolean, server_default="true"),
    Column("legacy_school_id",  Integer, nullable=True, index=True),   # source row in pre-migration schools.json
    Column("created_at",        DateTime, server_default=func.now()),
)
Index("ix_schools_kitchen_active", remote_schools.c.kitchen_id, remote_schools.c.is_active)

# --- School classes (Phase 1) — optional breakdown per grade
# Total `student_count` lives on the parent `schools` row for compatibility
# with existing allocation math; classes here are for finer forecasting later.
remote_school_classes = Table(
    "school_classes", remote_metadata,
    Column("id",            Integer, primary_key=True, autoincrement=True),
    Column("school_id",     Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("grade",         String(40), nullable=False),         # "Kelas 1", "PAUD A", etc.
    Column("student_count", Integer, nullable=False, server_default="0"),
    Column("age_group",     String(50), nullable=True),          # override if class differs from school default
    Column("created_at",    DateTime, server_default=func.now()),
)

# --- Purchase Orders (Phase 3) — Akuntan creates from Phase 2 forecast.
# Drives the Joint Inspection PO checklist when bahan datang.
remote_purchase_orders = Table(
    "purchase_orders", remote_metadata,
    Column("id",                     Integer, primary_key=True, autoincrement=True),
    Column("kitchen_id",             Integer, ForeignKey("kitchens.id"), nullable=False, index=True),
    Column("supplier_id",            Integer, ForeignKey("suppliers.id"), nullable=False, index=True),
    Column("status",                 String(20), server_default="draft"),  # draft | sent | partial | received | closed | cancelled
    Column("expected_delivery_date", Date, nullable=True, index=True),
    Column("total_amount_idr",       Integer, server_default="0"),
    Column("notes",                  Text, nullable=True),
    Column("created_by",             Integer, ForeignKey("users.id"), nullable=True),
    Column("created_at",             DateTime, server_default=func.now()),
    Column("sent_at",                DateTime, nullable=True),
    Column("received_at",            DateTime, nullable=True),
)
Index("ix_purchase_orders_kitchen_status", remote_purchase_orders.c.kitchen_id, remote_purchase_orders.c.status)

remote_po_lines = Table(
    "po_lines", remote_metadata,
    Column("id",                  Integer, primary_key=True, autoincrement=True),
    Column("po_id",               Integer, ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("item_name",           String(150), nullable=False),                # "Ayam Fillet"
    Column("item_code",           String(50), nullable=True),                  # optional TKPI code
    Column("total_weight_grams",  Integer, nullable=False),
    Column("unit",                String(20), server_default="kg"),
    Column("expected_containers", Integer, server_default="1"),                 # prediction: 200kg / 10kg = 20 box
    Column("unit_price_idr",      Integer, server_default="0"),                 # per unit (kg)
    Column("line_total_idr",      Integer, server_default="0"),
    Column("notes",               Text, nullable=True),
)

# --- Receiving Inspections (Phase 3) — 3-sign-off Joint Inspection
remote_receiving_inspections = Table(
    "receiving_inspections", remote_metadata,
    Column("id",            Integer, primary_key=True, autoincrement=True),
    Column("kitchen_id",    Integer, ForeignKey("kitchens.id"), nullable=False, index=True),
    Column("supplier_id",   Integer, ForeignKey("suppliers.id"), nullable=True, index=True),
    Column("po_id",         Integer, ForeignKey("purchase_orders.id"), nullable=True, index=True),
    Column("status",        String(20), server_default="pending"),   # pending | inspecting | accepted | rejected | partial
    Column("notes",         Text, nullable=True),
    Column("created_by",    Integer, ForeignKey("users.id"), nullable=True),
    Column("created_at",    DateTime, server_default=func.now()),
    Column("completed_at",  DateTime, nullable=True),
)
Index("ix_inspections_kitchen_status", remote_receiving_inspections.c.kitchen_id, remote_receiving_inspections.c.status)

# Per-PO-line outcome inside an inspection. ASLAP fills container_count + actual_weight.
remote_inspection_lines = Table(
    "inspection_lines", remote_metadata,
    Column("id",                    Integer, primary_key=True, autoincrement=True),
    Column("inspection_id",         Integer, ForeignKey("receiving_inspections.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("po_line_id",            Integer, ForeignKey("po_lines.id"), nullable=True),
    Column("item_name",             String(150), nullable=False),               # denormalized for audit clarity
    Column("expected_weight_grams", Integer, nullable=True),
    Column("actual_weight_grams",   Integer, nullable=True),
    Column("container_count",       Integer, server_default="0"),
    Column("storage_routing",       String(20), nullable=True),                 # 'cook_immediate' | 'refrigerate' | 'freeze'
    Column("status",                String(20), server_default="pending"),      # pending | accepted | rejected | partial
    Column("notes",                 Text, nullable=True),
    Column("created_at",            DateTime, server_default=func.now()),
)

# 3-sign-off audit trail. One row per role per inspection.
remote_inspection_signoffs = Table(
    "inspection_signoffs", remote_metadata,
    Column("id",              Integer, primary_key=True, autoincrement=True),
    Column("inspection_id",   Integer, ForeignKey("receiving_inspections.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("role_required",   String(20), nullable=False),    # 'quality' | 'quantity' | 'physical'
    Column("user_id",         Integer, ForeignKey("users.id"), nullable=True),
    Column("status",          String(20), nullable=False),    # 'approved' | 'rejected'
    Column("photo_path",      String(255), nullable=True),
    Column("notes",           Text, nullable=True),
    Column("is_offline_sign", Boolean, server_default="false"),  # foto tanda tangan kertas (Ahli Gizi/Akuntan tidak hadir)
    Column("signed_at",       DateTime, server_default=func.now()),
)
Index("ix_signoffs_inspection_role", remote_inspection_signoffs.c.inspection_id, remote_inspection_signoffs.c.role_required)

remote_supplier_disputes = Table(
    "supplier_disputes", remote_metadata,
    Column("id",                 Integer, primary_key=True, autoincrement=True),
    Column("kitchen_id",         Integer, ForeignKey("kitchens.id"), nullable=False, index=True),
    Column("supplier_id",        Integer, ForeignKey("suppliers.id"), nullable=True, index=True),
    Column("inspection_id",      Integer, ForeignKey("receiving_inspections.id"), nullable=True),
    Column("inspection_line_id", Integer, ForeignKey("inspection_lines.id"), nullable=True),
    Column("item_name",          String(150), nullable=True),
    Column("reason",             Text, nullable=True),
    Column("severity",           String(20), server_default="medium"),       # low | medium | high
    Column("photo_path",         String(255), nullable=True),
    Column("status",             String(20), server_default="open"),         # open | resolved | closed
    Column("created_by",         Integer, ForeignKey("users.id"), nullable=True),
    Column("created_at",         DateTime, server_default=func.now()),
    Column("resolved_at",        DateTime, nullable=True),
    Column("resolution_notes",   Text, nullable=True),
)
Index("ix_disputes_kitchen_status", remote_supplier_disputes.c.kitchen_id, remote_supplier_disputes.c.status)

# --- Suppliers (Phase 1) — vendor master per kitchen
remote_suppliers = Table(
    "suppliers", remote_metadata,
    Column("id",          Integer, primary_key=True, autoincrement=True),
    Column("kitchen_id",  Integer, ForeignKey("kitchens.id"), nullable=False, index=True),
    Column("name",        String(150), nullable=False),
    Column("contact",     String(100), nullable=True),       # phone / WA
    Column("npwp",        String(30), nullable=True),
    Column("rekening",    String(50), nullable=True),
    Column("bank_name",   String(50), nullable=True),
    Column("kategori",    String(50), nullable=True),        # "sayur" | "daging" | "beras" | etc.
    Column("rating",      Integer, server_default="5"),       # 1-5, defaults to 5 (untested)
    Column("notes",       Text, nullable=True),
    Column("is_active",   Boolean, server_default="true"),
    Column("created_at",  DateTime, server_default=func.now()),
)
Index("ix_suppliers_kitchen_active", remote_suppliers.c.kitchen_id, remote_suppliers.c.is_active)

# --- Production Batches (Phase 4) — Kepala Chef triggers from approved menu.
# 1 batch = 1 menu × target_porsi. Timer 4-6 jam SOP BGN starts on `started_at`.
remote_production_batches = Table(
    "production_batches", remote_metadata,
    Column("id",            Integer, primary_key=True, autoincrement=True),
    Column("kitchen_id",    Integer, ForeignKey("kitchens.id"), nullable=False, index=True),
    Column("menu_plan_id",  Integer, ForeignKey("saved_menus.id"), nullable=True, index=True),
    Column("menu_name",     String(150), nullable=True),       # denormalized for quick list
    Column("target_porsi",  Integer, nullable=False),
    Column("started_at",    DateTime, server_default=func.now()),
    Column("ended_at",      DateTime, nullable=True),
    Column("head_chef_id",  Integer, ForeignKey("users.id"), nullable=True),
    Column("status",        String(20), server_default="started"),   # started | qc_pending | qc_passed | ended | aborted
    Column("notes",         Text, nullable=True),
)
Index("ix_batches_kitchen_status", remote_production_batches.c.kitchen_id, remote_production_batches.c.status)

# Consumed items per batch (FIFO debit log). 1 row per item container consumed.
remote_batch_consumed_items = Table(
    "batch_consumed_items", remote_metadata,
    Column("id",          Integer, primary_key=True, autoincrement=True),
    Column("batch_id",    Integer, ForeignKey("production_batches.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("item_id",     String, ForeignKey("items.id"), nullable=False, index=True),
    Column("grams_used",  Integer, nullable=False),
    Column("ingredient_name", String(150), nullable=False),    # menu line name (denormalized)
    Column("consumed_at", DateTime, server_default=func.now()),
)

# Food samples retained 48h for QC audit (BGN: 1 porsi simpan kulkas tiap menu).
remote_food_samples = Table(
    "food_samples", remote_metadata,
    Column("id",          Integer, primary_key=True, autoincrement=True),
    Column("kitchen_id",  Integer, ForeignKey("kitchens.id"), nullable=False, index=True),
    Column("batch_id",    Integer, ForeignKey("production_batches.id"), nullable=False, index=True),
    Column("menu_name",   String(150), nullable=False),
    Column("photo_path",  String(255), nullable=True),
    Column("location",    String(100), nullable=True),         # e.g. "Kulkas A rak 2"
    Column("collected_by", Integer, ForeignKey("users.id"), nullable=True),
    Column("collected_at", DateTime, server_default=func.now()),
    Column("expire_at",   DateTime, nullable=False),           # +48h
    Column("status",      String(20), server_default="active"),  # active | expired | discarded
    Column("notes",       Text, nullable=True),
)
Index("ix_samples_kitchen_status", remote_food_samples.c.kitchen_id, remote_food_samples.c.status)

# --- Distribution layer (Phase 5) — extends existing scan flow:
#  • Existing _scan_allocations() smart batching kept untouched.
#  • These tables capture (a) guru-confirmed receipt at the school side,
#    (b) leftover porsi logging, (c) optional vehicle / driver assignment.
remote_delivery_confirmations = Table(
    "delivery_confirmations", remote_metadata,
    Column("id",              Integer, primary_key=True, autoincrement=True),
    Column("kitchen_id",      Integer, ForeignKey("kitchens.id"), nullable=True, index=True),
    Column("tray_id",         String, nullable=False, index=True),
    Column("school_id",       Integer, nullable=True, index=True),
    Column("school_name",     String(150), nullable=False),
    Column("confirmed_count", Integer, nullable=False),       # guru confirms how many ompreng received
    Column("ip_address",      String(45), nullable=True),
    Column("user_agent",      String(255), nullable=True),
    Column("notes",           Text, nullable=True),
    Column("photo_path",      String(255), nullable=True),
    Column("confirmed_at",    DateTime, server_default=func.now()),
)
Index("ix_delivery_confirmations_tray", remote_delivery_confirmations.c.tray_id)
Index("ix_delivery_confirmations_kitchen_at", remote_delivery_confirmations.c.kitchen_id, remote_delivery_confirmations.c.confirmed_at)

remote_delivery_leftovers = Table(
    "delivery_leftovers", remote_metadata,
    Column("id",           Integer, primary_key=True, autoincrement=True),
    Column("kitchen_id",   Integer, ForeignKey("kitchens.id"), nullable=False, index=True),
    Column("tray_id",      String, nullable=True, index=True),
    Column("school_id",    Integer, nullable=True, index=True),
    Column("school_name",  String(150), nullable=True),
    Column("qty",          Integer, nullable=False),
    Column("kategori",     String(20), nullable=False),       # 'return' | 'extra' | 'disposal'
    Column("photo_path",   String(255), nullable=True),
    Column("notes",        Text, nullable=True),
    Column("created_by",   Integer, ForeignKey("users.id"), nullable=True),
    Column("created_at",   DateTime, server_default=func.now()),
    Column("created_date", Date, index=True),
)
Index("ix_leftovers_kitchen_date", remote_delivery_leftovers.c.kitchen_id, remote_delivery_leftovers.c.created_date)

remote_vehicles = Table(
    "vehicles", remote_metadata,
    Column("id",              Integer, primary_key=True, autoincrement=True),
    Column("kitchen_id",      Integer, ForeignKey("kitchens.id"), nullable=False, index=True),
    Column("plate",           String(20), nullable=False),
    Column("model",           String(100), nullable=True),
    Column("capacity_porsi",  Integer, server_default="0"),
    Column("is_active",       Boolean, server_default="true"),
    Column("created_at",      DateTime, server_default=func.now()),
)

remote_drivers = Table(
    "drivers", remote_metadata,
    Column("id",            Integer, primary_key=True, autoincrement=True),
    Column("kitchen_id",    Integer, ForeignKey("kitchens.id"), nullable=False, index=True),
    Column("name",          String(150), nullable=False),
    Column("phone",         String(30), nullable=True),
    Column("license_no",    String(40), nullable=True),
    Column("is_active",     Boolean, server_default="true"),
    Column("created_at",    DateTime, server_default=func.now()),
)

# --- Akuntan finance module (Phase 6) — expense tracker + LRA biweekly
remote_expenses = Table(
    "expenses", remote_metadata,
    Column("id",             Integer, primary_key=True, autoincrement=True),
    Column("kitchen_id",     Integer, ForeignKey("kitchens.id"), nullable=False, index=True),
    Column("category",       String(20), nullable=False, index=True),   # bahan|listrik|gas|air|internet|honor|bbm|lainnya
    Column("amount_idr",     Integer, nullable=False),
    Column("expense_date",   Date, nullable=False, index=True),
    Column("supplier_id",    Integer, ForeignKey("suppliers.id"), nullable=True),
    Column("po_id",          Integer, ForeignKey("purchase_orders.id"), nullable=True),
    Column("evidence_photo", String(255), nullable=True),
    Column("notes",          Text, nullable=True),
    Column("created_by",     Integer, ForeignKey("users.id"), nullable=True),
    Column("created_at",     DateTime, server_default=func.now()),
)
Index("ix_expenses_kitchen_date", remote_expenses.c.kitchen_id, remote_expenses.c.expense_date)
Index("ix_expenses_kitchen_category_date", remote_expenses.c.kitchen_id, remote_expenses.c.category, remote_expenses.c.expense_date)

# Honor relawan harian (sub-form expenses with per-volunteer breakdown).
remote_volunteer_payments = Table(
    "volunteer_payments", remote_metadata,
    Column("id",            Integer, primary_key=True, autoincrement=True),
    Column("kitchen_id",    Integer, ForeignKey("kitchens.id"), nullable=False, index=True),
    Column("name",          String(150), nullable=False),
    Column("hours_worked",  Integer, server_default="0"),
    Column("hourly_rate",   Integer, server_default="0"),
    Column("total_amount",  Integer, nullable=False),
    Column("work_date",     Date, nullable=False, index=True),
    Column("notes",         Text, nullable=True),
    Column("created_by",    Integer, ForeignKey("users.id"), nullable=True),
    Column("created_at",    DateTime, server_default=func.now()),
)
Index("ix_volunteer_kitchen_date", remote_volunteer_payments.c.kitchen_id, remote_volunteer_payments.c.work_date)

# LRA biweekly periods — generated snapshot ke BGN.
remote_lra_periods = Table(
    "lra_periods", remote_metadata,
    Column("id",                Integer, primary_key=True, autoincrement=True),
    Column("kitchen_id",        Integer, ForeignKey("kitchens.id"), nullable=False, index=True),
    Column("period_start",      Date, nullable=False, index=True),
    Column("period_end",        Date, nullable=False),
    Column("status",            String(20), server_default="draft"),   # draft | generated | submitted
    Column("total_revenue_idr", Integer, server_default="0"),
    Column("total_expense_idr", Integer, server_default="0"),
    Column("total_porsi",       Integer, server_default="0"),
    Column("cost_per_porsi",    Integer, server_default="0"),
    Column("breakdown_json",    Text, nullable=True),                   # full JSON snapshot per category + bahan
    Column("notes",             Text, nullable=True),
    Column("generated_by",      Integer, ForeignKey("users.id"), nullable=True),
    Column("generated_at",      DateTime, nullable=True),
    Column("submitted_at",      DateTime, nullable=True),
)
Index("ix_lra_kitchen_period", remote_lra_periods.c.kitchen_id, remote_lra_periods.c.period_start)

# --- ASLAP daily ops (Phase 7) — checklist + water quality + observations + comms
remote_daily_checklists = Table(
    "daily_checklists", remote_metadata,
    Column("id",            Integer, primary_key=True, autoincrement=True),
    Column("kitchen_id",    Integer, ForeignKey("kitchens.id"), nullable=False, index=True),
    Column("checklist_date", Date, nullable=False, index=True),
    Column("items_json",    Text, nullable=False),       # [{key, label, type, required, value, photo, ok}]
    Column("status",        String(20), server_default="draft"),  # draft | submitted
    Column("submitted_by",  Integer, ForeignKey("users.id"), nullable=True),
    Column("submitted_at",  DateTime, nullable=True),
    Column("notes",         Text, nullable=True),
    Column("created_at",    DateTime, server_default=func.now()),
)
Index("ix_checklists_kitchen_date", remote_daily_checklists.c.kitchen_id, remote_daily_checklists.c.checklist_date)

remote_water_quality_logs = Table(
    "water_quality_logs", remote_metadata,
    Column("id",          Integer, primary_key=True, autoincrement=True),
    Column("kitchen_id",  Integer, ForeignKey("kitchens.id"), nullable=False, index=True),
    Column("log_date",    Date, nullable=False, index=True),
    Column("tds_ppm",     Integer, nullable=True),         # threshold: ≤500 OK
    Column("ph",          String(8), nullable=True),       # threshold: 6.5-8.5 OK
    Column("bau",         String(20), nullable=True),      # 'normal' | 'amis' | 'kimia' | dst.
    Column("warna",       String(20), nullable=True),      # 'jernih' | 'keruh' | 'kuning'
    Column("photo_path",  String(255), nullable=True),
    Column("tester_id",   Integer, ForeignKey("users.id"), nullable=True),
    Column("alert_flags", Text, nullable=True),            # JSON of triggered alerts
    Column("notes",       Text, nullable=True),
    Column("created_at",  DateTime, server_default=func.now()),
)
Index("ix_water_kitchen_date", remote_water_quality_logs.c.kitchen_id, remote_water_quality_logs.c.log_date)

remote_production_observations = Table(
    "production_observations", remote_metadata,
    Column("id",              Integer, primary_key=True, autoincrement=True),
    Column("kitchen_id",      Integer, ForeignKey("kitchens.id"), nullable=False, index=True),
    Column("batch_id",        Integer, ForeignKey("production_batches.id"), nullable=True, index=True),
    Column("observer_id",     Integer, ForeignKey("users.id"), nullable=True),
    Column("suhu_masak",      Integer, nullable=True),         # celsius
    Column("waktu_menit",     Integer, nullable=True),
    Column("kebersihan_ok",   Boolean, server_default="true"),
    Column("photo_path",      String(255), nullable=True),
    Column("notes",           Text, nullable=True),
    Column("observed_at",     DateTime, server_default=func.now()),
)
Index("ix_obs_kitchen_observed", remote_production_observations.c.kitchen_id, remote_production_observations.c.observed_at)

remote_school_comm_logs = Table(
    "school_comm_logs", remote_metadata,
    Column("id",          Integer, primary_key=True, autoincrement=True),
    Column("kitchen_id",  Integer, ForeignKey("kitchens.id"), nullable=False, index=True),
    Column("school_id",   Integer, ForeignKey("schools.id", ondelete="SET NULL"), nullable=True, index=True),
    Column("school_name", String(150), nullable=True),
    Column("channel",     String(20), nullable=False),     # 'call' | 'wa' | 'email' | 'visit'
    Column("topic",       String(150), nullable=False),
    Column("response",    Text, nullable=True),
    Column("follow_up",   Boolean, server_default="false"),
    Column("created_by",  Integer, ForeignKey("users.id"), nullable=True),
    Column("created_at",  DateTime, server_default=func.now()),
)
Index("ix_comm_kitchen_at", remote_school_comm_logs.c.kitchen_id, remote_school_comm_logs.c.created_at)

remote_aslap_weekly_reports = Table(
    "aslap_weekly_reports", remote_metadata,
    Column("id",            Integer, primary_key=True, autoincrement=True),
    Column("kitchen_id",    Integer, ForeignKey("kitchens.id"), nullable=False, index=True),
    Column("week_start",    Date, nullable=False, index=True),
    Column("week_end",      Date, nullable=False),
    Column("summary_json",  Text, nullable=False),         # snapshot blob
    Column("status",        String(20), server_default="draft"),  # draft | submitted
    Column("generated_by",  Integer, ForeignKey("users.id"), nullable=True),
    Column("generated_at",  DateTime, server_default=func.now()),
    Column("submitted_at",  DateTime, nullable=True),
)
Index("ix_aslap_reports_kitchen_week", remote_aslap_weekly_reports.c.kitchen_id, remote_aslap_weekly_reports.c.week_start)

# --- Notifications (Phase 8) — in-app + SSE + (future) push PWA
remote_notifications = Table(
    "notifications", remote_metadata,
    Column("id",          Integer, primary_key=True, autoincrement=True),
    Column("user_id",     Integer, ForeignKey("users.id"), nullable=False, index=True),
    Column("kitchen_id",  Integer, ForeignKey("kitchens.id"), nullable=True, index=True),
    Column("type",        String(50), nullable=False, index=True),  # menu.pending_review | inspection.scheduled | etc.
    Column("category",    String(20), nullable=False, index=True),  # menu | receiving | production | distribution | finance | compliance | system
    Column("title",       String(150), nullable=False),
    Column("body",        Text, nullable=True),
    Column("payload_json", Text, nullable=True),                     # extra context (link, ids, etc.)
    Column("link",        String(255), nullable=True),               # frontend route to navigate on click
    Column("read_at",     DateTime, nullable=True, index=True),
    Column("created_at",  DateTime, server_default=func.now(), index=True),
)
Index("ix_notifications_user_unread", remote_notifications.c.user_id, remote_notifications.c.read_at, remote_notifications.c.created_at)

remote_notification_subscriptions = Table(
    "notification_subscriptions", remote_metadata,
    Column("id",         Integer, primary_key=True, autoincrement=True),
    Column("user_id",    Integer, ForeignKey("users.id"), nullable=False, index=True),
    Column("endpoint",   Text, nullable=False),
    Column("p256dh",     String(255), nullable=True),
    Column("auth",       String(255), nullable=True),
    Column("user_agent", String(255), nullable=True),
    Column("created_at", DateTime, server_default=func.now()),
)

remote_notification_preferences = Table(
    "notification_preferences", remote_metadata,
    Column("id",         Integer, primary_key=True, autoincrement=True),
    Column("user_id",    Integer, ForeignKey("users.id"), nullable=False, index=True),
    Column("category",   String(20), nullable=False),
    Column("enabled",    Boolean, server_default="true"),
    UniqueConstraint("user_id", "category", name="uq_notif_pref_user_category"),
)

# --- Schema migrations registry (Phase 0)
# Tracks which versioned migrations have been applied. Idempotent helper for
# future phases that need ordered, named migrations beyond the catch-all
# `_online_migrate()` ALTER TABLE list.
remote_schema_migrations = Table(
    "schema_migrations", remote_metadata,
    Column("version",     String(50), primary_key=True),  # e.g. "001_initial", "003_audit_log_expansion"
    Column("applied_at",  DateTime, server_default=func.now()),
    Column("description", String(255), nullable=True),
)

# --- Defect items (rejected on receiving QC) — mirrors items + photo + reason
# Separated from `items` because the workflow is distinct: defect rows never
# enter the processing/packing/delivery pipeline. They exist for supplier
# accountability and BGN audit reporting.
remote_defect_items = Table(
    "defect_items", remote_metadata,
    Column("id",            String, primary_key=True),                         # DEF-XXXXXXXX
    Column("kitchen_id",    Integer, ForeignKey("kitchens.id"), nullable=False, index=True),
    Column("name",          String, nullable=False),
    Column("weight_grams",  Integer, nullable=False),
    Column("unit",          String, nullable=False),
    Column("reason",        Text),                                              # JSON: {checklist, notes, defect_reason}
    Column("photo_path",    String(255), nullable=True),                        # relative path under data/defect_photos/
    Column("item_id",       String, ForeignKey("items.id", ondelete="SET NULL"), nullable=True, index=True),
    Column("created_by",    Integer, ForeignKey("users.id"), nullable=True),
    Column("created_at",    DateTime, server_default=func.now()),
    Column("created_date",  Date, index=True),
)
Index("ix_defect_items_kitchen_date", remote_defect_items.c.kitchen_id, remote_defect_items.c.created_date)

# ============================================================
# INIT
# ============================================================

def init_db():
    """Create local SQLite tables. Call once on scanner startup."""
    local_metadata.create_all(local_engine)


def init_remote_db():
    """Create remote PostgreSQL tables (food_prices etc). Safe to call on startup."""
    if remote_engine:
        remote_metadata.create_all(remote_engine)
        _online_migrate()


def _online_migrate():
    """Add columns that may be missing on older deployments. Idempotent."""
    from sqlalchemy import text as _text
    stmts = [
        "ALTER TABLE food_prices ADD COLUMN IF NOT EXISTS manual_price INTEGER",
        "ALTER TABLE food_prices ADD COLUMN IF NOT EXISTS manual_source VARCHAR(255)",
        "ALTER TABLE food_prices ADD COLUMN IF NOT EXISTS manual_set_by INTEGER",
        "ALTER TABLE food_prices ADD COLUMN IF NOT EXISTS manual_set_at TIMESTAMP",
        """CREATE TABLE IF NOT EXISTS saved_menus (
            id SERIAL PRIMARY KEY,
            kitchen_id INTEGER NOT NULL REFERENCES kitchens(id),
            name VARCHAR(150) NOT NULL,
            created_by INTEGER NOT NULL REFERENCES users(id),
            created_at TIMESTAMP DEFAULT NOW(),
            payload TEXT NOT NULL
        )""",
        "CREATE INDEX IF NOT EXISTS ix_saved_menus_kitchen_created ON saved_menus (kitchen_id, created_at DESC)",
        """CREATE TABLE IF NOT EXISTS audit_log (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP DEFAULT NOW(),
            user_id INTEGER NULL,
            kitchen_id INTEGER NULL,
            org_id INTEGER NULL,
            action VARCHAR(80) NOT NULL,
            target_type VARCHAR(50) NULL,
            target_id VARCHAR(100) NULL,
            ip_address VARCHAR(45) NULL,
            details TEXT NULL
        )""",
        "CREATE INDEX IF NOT EXISTS ix_audit_log_action_created ON audit_log (action, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS ix_audit_log_user ON audit_log (user_id, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS ix_audit_log_kitchen ON audit_log (kitchen_id, created_at DESC)",
        """CREATE TABLE IF NOT EXISTS defect_items (
            id VARCHAR PRIMARY KEY,
            kitchen_id INTEGER NOT NULL REFERENCES kitchens(id),
            name VARCHAR NOT NULL,
            weight_grams INTEGER NOT NULL,
            unit VARCHAR NOT NULL,
            reason TEXT,
            photo_path VARCHAR(255),
            created_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT NOW(),
            created_date DATE
        )""",
        "CREATE INDEX IF NOT EXISTS ix_defect_items_kitchen_date ON defect_items (kitchen_id, created_date DESC)",
        # items.id is a non-PK string column (scan_id is the PK). Add a UNIQUE
        # constraint so we can reference it via FK from defect_items.item_id.
        "ALTER TABLE items ADD CONSTRAINT uq_items_id UNIQUE (id)",
        "ALTER TABLE defect_items ADD COLUMN IF NOT EXISTS item_id VARCHAR REFERENCES items(id) ON DELETE SET NULL",
        "CREATE INDEX IF NOT EXISTS ix_defect_items_item_id ON defect_items (item_id)",
        # Phase 0 — audit_log expansion (before/after value snapshots + category)
        "ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS event_category VARCHAR(30)",
        "ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS before_value TEXT",
        "ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS after_value TEXT",
        "CREATE INDEX IF NOT EXISTS ix_audit_log_event_category ON audit_log (event_category, created_at DESC)",
        # Phase 0 — schema migrations registry
        """CREATE TABLE IF NOT EXISTS schema_migrations (
            version VARCHAR(50) PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT NOW(),
            description VARCHAR(255)
        )""",
        # If table existed pre-fix with VARCHAR(20), widen the column. NO-OP after first run.
        "ALTER TABLE schema_migrations ALTER COLUMN version TYPE VARCHAR(50)",
        # Phase 1 — schools + school_classes + suppliers + items.default_supplier_id
        """CREATE TABLE IF NOT EXISTS schools (
            id SERIAL PRIMARY KEY,
            kitchen_id INTEGER NOT NULL REFERENCES kitchens(id),
            name VARCHAR(150) NOT NULL,
            address TEXT,
            level VARCHAR(20) NOT NULL,
            age_group VARCHAR(50) NOT NULL,
            student_count INTEGER NOT NULL DEFAULT 0,
            distance INTEGER NOT NULL DEFAULT 0,
            gps_lat VARCHAR(20),
            gps_long VARCHAR(20),
            contact VARCHAR(100),
            is_active BOOLEAN DEFAULT TRUE,
            legacy_school_id INTEGER,
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        "CREATE INDEX IF NOT EXISTS ix_schools_kitchen_active ON schools (kitchen_id, is_active)",
        "CREATE INDEX IF NOT EXISTS ix_schools_legacy_id ON schools (legacy_school_id)",
        """CREATE TABLE IF NOT EXISTS school_classes (
            id SERIAL PRIMARY KEY,
            school_id INTEGER NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
            grade VARCHAR(40) NOT NULL,
            student_count INTEGER NOT NULL DEFAULT 0,
            age_group VARCHAR(50),
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        "CREATE INDEX IF NOT EXISTS ix_school_classes_school ON school_classes (school_id)",
        """CREATE TABLE IF NOT EXISTS suppliers (
            id SERIAL PRIMARY KEY,
            kitchen_id INTEGER NOT NULL REFERENCES kitchens(id),
            name VARCHAR(150) NOT NULL,
            contact VARCHAR(100),
            npwp VARCHAR(30),
            rekening VARCHAR(50),
            bank_name VARCHAR(50),
            kategori VARCHAR(50),
            rating INTEGER DEFAULT 5,
            notes TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        "CREATE INDEX IF NOT EXISTS ix_suppliers_kitchen_active ON suppliers (kitchen_id, is_active)",
        "ALTER TABLE items ADD COLUMN IF NOT EXISTS default_supplier_id INTEGER REFERENCES suppliers(id) ON DELETE SET NULL",
        "CREATE INDEX IF NOT EXISTS ix_items_default_supplier ON items (default_supplier_id)",
        # Phase 2 — saved_menus approval workflow + target date + source flag
        "ALTER TABLE saved_menus ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'draft'",
        "ALTER TABLE saved_menus ADD COLUMN IF NOT EXISTS source VARCHAR(20) DEFAULT 'optimizer'",
        "ALTER TABLE saved_menus ADD COLUMN IF NOT EXISTS target_date DATE",
        "ALTER TABLE saved_menus ADD COLUMN IF NOT EXISTS target_school_id INTEGER",
        "ALTER TABLE saved_menus ADD COLUMN IF NOT EXISTS submitted_at TIMESTAMP",
        "ALTER TABLE saved_menus ADD COLUMN IF NOT EXISTS submitted_by INTEGER",
        "ALTER TABLE saved_menus ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP",
        "ALTER TABLE saved_menus ADD COLUMN IF NOT EXISTS approved_by INTEGER",
        "ALTER TABLE saved_menus ADD COLUMN IF NOT EXISTS review_notes TEXT",
        "CREATE INDEX IF NOT EXISTS ix_saved_menus_status_date ON saved_menus (kitchen_id, status, target_date)",
        # Phase 2 — student_requests
        """CREATE TABLE IF NOT EXISTS student_requests (
            id SERIAL PRIMARY KEY,
            kitchen_id INTEGER NOT NULL REFERENCES kitchens(id),
            school_id INTEGER REFERENCES schools(id) ON DELETE SET NULL,
            kelas VARCHAR(40),
            student_name VARCHAR(100),
            request_text TEXT NOT NULL,
            status VARCHAR(20) DEFAULT 'open',
            ahli_gizi_notes TEXT,
            created_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT NOW(),
            resolved_by INTEGER,
            resolved_at TIMESTAMP
        )""",
        "CREATE INDEX IF NOT EXISTS ix_student_requests_kitchen_status ON student_requests (kitchen_id, status)",
        # Phase 3 — Purchase Orders + lines
        """CREATE TABLE IF NOT EXISTS purchase_orders (
            id SERIAL PRIMARY KEY,
            kitchen_id INTEGER NOT NULL REFERENCES kitchens(id),
            supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
            status VARCHAR(20) DEFAULT 'draft',
            expected_delivery_date DATE,
            total_amount_idr INTEGER DEFAULT 0,
            notes TEXT,
            created_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT NOW(),
            sent_at TIMESTAMP,
            received_at TIMESTAMP
        )""",
        "CREATE INDEX IF NOT EXISTS ix_purchase_orders_kitchen_status ON purchase_orders (kitchen_id, status)",
        """CREATE TABLE IF NOT EXISTS po_lines (
            id SERIAL PRIMARY KEY,
            po_id INTEGER NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
            item_name VARCHAR(150) NOT NULL,
            item_code VARCHAR(50),
            total_weight_grams INTEGER NOT NULL,
            unit VARCHAR(20) DEFAULT 'kg',
            expected_containers INTEGER DEFAULT 1,
            unit_price_idr INTEGER DEFAULT 0,
            line_total_idr INTEGER DEFAULT 0,
            notes TEXT
        )""",
        "CREATE INDEX IF NOT EXISTS ix_po_lines_po ON po_lines (po_id)",
        # Phase 3 — Receiving Inspections + 3-sign-off + per-line outcome + disputes
        """CREATE TABLE IF NOT EXISTS receiving_inspections (
            id SERIAL PRIMARY KEY,
            kitchen_id INTEGER NOT NULL REFERENCES kitchens(id),
            supplier_id INTEGER REFERENCES suppliers(id),
            po_id INTEGER REFERENCES purchase_orders(id),
            status VARCHAR(20) DEFAULT 'pending',
            notes TEXT,
            created_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT NOW(),
            completed_at TIMESTAMP
        )""",
        "CREATE INDEX IF NOT EXISTS ix_inspections_kitchen_status ON receiving_inspections (kitchen_id, status)",
        """CREATE TABLE IF NOT EXISTS inspection_lines (
            id SERIAL PRIMARY KEY,
            inspection_id INTEGER NOT NULL REFERENCES receiving_inspections(id) ON DELETE CASCADE,
            po_line_id INTEGER REFERENCES po_lines(id),
            item_name VARCHAR(150) NOT NULL,
            expected_weight_grams INTEGER,
            actual_weight_grams INTEGER,
            container_count INTEGER DEFAULT 0,
            storage_routing VARCHAR(20),
            status VARCHAR(20) DEFAULT 'pending',
            notes TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        "CREATE INDEX IF NOT EXISTS ix_inspection_lines_inspection ON inspection_lines (inspection_id)",
        """CREATE TABLE IF NOT EXISTS inspection_signoffs (
            id SERIAL PRIMARY KEY,
            inspection_id INTEGER NOT NULL REFERENCES receiving_inspections(id) ON DELETE CASCADE,
            role_required VARCHAR(20) NOT NULL,
            user_id INTEGER REFERENCES users(id),
            status VARCHAR(20) NOT NULL,
            photo_path VARCHAR(255),
            notes TEXT,
            is_offline_sign BOOLEAN DEFAULT FALSE,
            signed_at TIMESTAMP DEFAULT NOW()
        )""",
        "CREATE INDEX IF NOT EXISTS ix_signoffs_inspection_role ON inspection_signoffs (inspection_id, role_required)",
        """CREATE TABLE IF NOT EXISTS supplier_disputes (
            id SERIAL PRIMARY KEY,
            kitchen_id INTEGER NOT NULL REFERENCES kitchens(id),
            supplier_id INTEGER REFERENCES suppliers(id),
            inspection_id INTEGER REFERENCES receiving_inspections(id),
            inspection_line_id INTEGER REFERENCES inspection_lines(id),
            item_name VARCHAR(150),
            reason TEXT,
            severity VARCHAR(20) DEFAULT 'medium',
            photo_path VARCHAR(255),
            status VARCHAR(20) DEFAULT 'open',
            created_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT NOW(),
            resolved_at TIMESTAMP,
            resolution_notes TEXT
        )""",
        "CREATE INDEX IF NOT EXISTS ix_disputes_kitchen_status ON supplier_disputes (kitchen_id, status)",
        # Phase 3 — items linkage to po_line + inspection_line + storage routing
        "ALTER TABLE items ADD COLUMN IF NOT EXISTS parent_po_line_id INTEGER REFERENCES po_lines(id) ON DELETE SET NULL",
        "ALTER TABLE items ADD COLUMN IF NOT EXISTS inspection_line_id INTEGER REFERENCES inspection_lines(id) ON DELETE SET NULL",
        "ALTER TABLE items ADD COLUMN IF NOT EXISTS storage_routing VARCHAR(20)",
        "CREATE INDEX IF NOT EXISTS ix_items_parent_po_line ON items (parent_po_line_id)",
        "CREATE INDEX IF NOT EXISTS ix_items_inspection_line ON items (inspection_line_id)",
        # Phase 4 — production_batches + consumed_items + food_samples
        """CREATE TABLE IF NOT EXISTS production_batches (
            id SERIAL PRIMARY KEY,
            kitchen_id INTEGER NOT NULL REFERENCES kitchens(id),
            menu_plan_id INTEGER REFERENCES saved_menus(id),
            menu_name VARCHAR(150),
            target_porsi INTEGER NOT NULL,
            started_at TIMESTAMP DEFAULT NOW(),
            ended_at TIMESTAMP,
            head_chef_id INTEGER REFERENCES users(id),
            status VARCHAR(20) DEFAULT 'started',
            notes TEXT
        )""",
        "CREATE INDEX IF NOT EXISTS ix_batches_kitchen_status ON production_batches (kitchen_id, status)",
        """CREATE TABLE IF NOT EXISTS batch_consumed_items (
            id SERIAL PRIMARY KEY,
            batch_id INTEGER NOT NULL REFERENCES production_batches(id) ON DELETE CASCADE,
            item_id VARCHAR NOT NULL REFERENCES items(id),
            grams_used INTEGER NOT NULL,
            ingredient_name VARCHAR(150) NOT NULL,
            consumed_at TIMESTAMP DEFAULT NOW()
        )""",
        "CREATE INDEX IF NOT EXISTS ix_batch_consumed_batch ON batch_consumed_items (batch_id)",
        "CREATE INDEX IF NOT EXISTS ix_batch_consumed_item ON batch_consumed_items (item_id)",
        """CREATE TABLE IF NOT EXISTS food_samples (
            id SERIAL PRIMARY KEY,
            kitchen_id INTEGER NOT NULL REFERENCES kitchens(id),
            batch_id INTEGER NOT NULL REFERENCES production_batches(id),
            menu_name VARCHAR(150) NOT NULL,
            photo_path VARCHAR(255),
            location VARCHAR(100),
            collected_by INTEGER REFERENCES users(id),
            collected_at TIMESTAMP DEFAULT NOW(),
            expire_at TIMESTAMP NOT NULL,
            status VARCHAR(20) DEFAULT 'active',
            notes TEXT
        )""",
        "CREATE INDEX IF NOT EXISTS ix_samples_kitchen_status ON food_samples (kitchen_id, status)",
        # Phase 5 — Distribution layer (delivery_confirmations + leftovers + vehicles + drivers)
        """CREATE TABLE IF NOT EXISTS delivery_confirmations (
            id SERIAL PRIMARY KEY,
            kitchen_id INTEGER REFERENCES kitchens(id),
            tray_id VARCHAR NOT NULL,
            school_id INTEGER,
            school_name VARCHAR(150) NOT NULL,
            confirmed_count INTEGER NOT NULL,
            ip_address VARCHAR(45),
            user_agent VARCHAR(255),
            notes TEXT,
            photo_path VARCHAR(255),
            confirmed_at TIMESTAMP DEFAULT NOW()
        )""",
        "CREATE INDEX IF NOT EXISTS ix_delivery_confirmations_tray ON delivery_confirmations (tray_id)",
        "CREATE INDEX IF NOT EXISTS ix_delivery_confirmations_kitchen_at ON delivery_confirmations (kitchen_id, confirmed_at DESC)",
        """CREATE TABLE IF NOT EXISTS delivery_leftovers (
            id SERIAL PRIMARY KEY,
            kitchen_id INTEGER NOT NULL REFERENCES kitchens(id),
            tray_id VARCHAR,
            school_id INTEGER,
            school_name VARCHAR(150),
            qty INTEGER NOT NULL,
            kategori VARCHAR(20) NOT NULL,
            photo_path VARCHAR(255),
            notes TEXT,
            created_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT NOW(),
            created_date DATE
        )""",
        "CREATE INDEX IF NOT EXISTS ix_leftovers_kitchen_date ON delivery_leftovers (kitchen_id, created_date DESC)",
        """CREATE TABLE IF NOT EXISTS vehicles (
            id SERIAL PRIMARY KEY,
            kitchen_id INTEGER NOT NULL REFERENCES kitchens(id),
            plate VARCHAR(20) NOT NULL,
            model VARCHAR(100),
            capacity_porsi INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS drivers (
            id SERIAL PRIMARY KEY,
            kitchen_id INTEGER NOT NULL REFERENCES kitchens(id),
            name VARCHAR(150) NOT NULL,
            phone VARCHAR(30),
            license_no VARCHAR(40),
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        # Phase 6 — finance: expenses + volunteer_payments + lra_periods
        """CREATE TABLE IF NOT EXISTS expenses (
            id SERIAL PRIMARY KEY,
            kitchen_id INTEGER NOT NULL REFERENCES kitchens(id),
            category VARCHAR(20) NOT NULL,
            amount_idr INTEGER NOT NULL,
            expense_date DATE NOT NULL,
            supplier_id INTEGER REFERENCES suppliers(id),
            po_id INTEGER REFERENCES purchase_orders(id),
            evidence_photo VARCHAR(255),
            notes TEXT,
            created_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        "CREATE INDEX IF NOT EXISTS ix_expenses_kitchen_date ON expenses (kitchen_id, expense_date)",
        "CREATE INDEX IF NOT EXISTS ix_expenses_kitchen_category_date ON expenses (kitchen_id, category, expense_date)",
        """CREATE TABLE IF NOT EXISTS volunteer_payments (
            id SERIAL PRIMARY KEY,
            kitchen_id INTEGER NOT NULL REFERENCES kitchens(id),
            name VARCHAR(150) NOT NULL,
            hours_worked INTEGER DEFAULT 0,
            hourly_rate INTEGER DEFAULT 0,
            total_amount INTEGER NOT NULL,
            work_date DATE NOT NULL,
            notes TEXT,
            created_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        "CREATE INDEX IF NOT EXISTS ix_volunteer_kitchen_date ON volunteer_payments (kitchen_id, work_date)",
        """CREATE TABLE IF NOT EXISTS lra_periods (
            id SERIAL PRIMARY KEY,
            kitchen_id INTEGER NOT NULL REFERENCES kitchens(id),
            period_start DATE NOT NULL,
            period_end DATE NOT NULL,
            status VARCHAR(20) DEFAULT 'draft',
            total_revenue_idr INTEGER DEFAULT 0,
            total_expense_idr INTEGER DEFAULT 0,
            total_porsi INTEGER DEFAULT 0,
            cost_per_porsi INTEGER DEFAULT 0,
            breakdown_json TEXT,
            notes TEXT,
            generated_by INTEGER REFERENCES users(id),
            generated_at TIMESTAMP,
            submitted_at TIMESTAMP
        )""",
        "CREATE INDEX IF NOT EXISTS ix_lra_kitchen_period ON lra_periods (kitchen_id, period_start)",
        # Phase 7 — ASLAP daily ops: checklists + water quality + observations + comm logs + weekly reports
        """CREATE TABLE IF NOT EXISTS daily_checklists (
            id SERIAL PRIMARY KEY,
            kitchen_id INTEGER NOT NULL REFERENCES kitchens(id),
            checklist_date DATE NOT NULL,
            items_json TEXT NOT NULL,
            status VARCHAR(20) DEFAULT 'draft',
            submitted_by INTEGER REFERENCES users(id),
            submitted_at TIMESTAMP,
            notes TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        "CREATE INDEX IF NOT EXISTS ix_checklists_kitchen_date ON daily_checklists (kitchen_id, checklist_date)",
        """CREATE TABLE IF NOT EXISTS water_quality_logs (
            id SERIAL PRIMARY KEY,
            kitchen_id INTEGER NOT NULL REFERENCES kitchens(id),
            log_date DATE NOT NULL,
            tds_ppm INTEGER,
            ph VARCHAR(8),
            bau VARCHAR(20),
            warna VARCHAR(20),
            photo_path VARCHAR(255),
            tester_id INTEGER REFERENCES users(id),
            alert_flags TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        "CREATE INDEX IF NOT EXISTS ix_water_kitchen_date ON water_quality_logs (kitchen_id, log_date)",
        """CREATE TABLE IF NOT EXISTS production_observations (
            id SERIAL PRIMARY KEY,
            kitchen_id INTEGER NOT NULL REFERENCES kitchens(id),
            batch_id INTEGER REFERENCES production_batches(id),
            observer_id INTEGER REFERENCES users(id),
            suhu_masak INTEGER,
            waktu_menit INTEGER,
            kebersihan_ok BOOLEAN DEFAULT TRUE,
            photo_path VARCHAR(255),
            notes TEXT,
            observed_at TIMESTAMP DEFAULT NOW()
        )""",
        "CREATE INDEX IF NOT EXISTS ix_obs_kitchen_observed ON production_observations (kitchen_id, observed_at)",
        """CREATE TABLE IF NOT EXISTS school_comm_logs (
            id SERIAL PRIMARY KEY,
            kitchen_id INTEGER NOT NULL REFERENCES kitchens(id),
            school_id INTEGER REFERENCES schools(id) ON DELETE SET NULL,
            school_name VARCHAR(150),
            channel VARCHAR(20) NOT NULL,
            topic VARCHAR(150) NOT NULL,
            response TEXT,
            follow_up BOOLEAN DEFAULT FALSE,
            created_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        "CREATE INDEX IF NOT EXISTS ix_comm_kitchen_at ON school_comm_logs (kitchen_id, created_at)",
        """CREATE TABLE IF NOT EXISTS aslap_weekly_reports (
            id SERIAL PRIMARY KEY,
            kitchen_id INTEGER NOT NULL REFERENCES kitchens(id),
            week_start DATE NOT NULL,
            week_end DATE NOT NULL,
            summary_json TEXT NOT NULL,
            status VARCHAR(20) DEFAULT 'draft',
            generated_by INTEGER REFERENCES users(id),
            generated_at TIMESTAMP DEFAULT NOW(),
            submitted_at TIMESTAMP
        )""",
        "CREATE INDEX IF NOT EXISTS ix_aslap_reports_kitchen_week ON aslap_weekly_reports (kitchen_id, week_start)",
        # Phase 8 — notifications + push subscriptions + preferences
        """CREATE TABLE IF NOT EXISTS notifications (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            kitchen_id INTEGER REFERENCES kitchens(id),
            type VARCHAR(50) NOT NULL,
            category VARCHAR(20) NOT NULL,
            title VARCHAR(150) NOT NULL,
            body TEXT,
            payload_json TEXT,
            link VARCHAR(255),
            read_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        "CREATE INDEX IF NOT EXISTS ix_notifications_user_unread ON notifications (user_id, read_at, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS ix_notifications_kitchen ON notifications (kitchen_id, created_at DESC)",
        """CREATE TABLE IF NOT EXISTS notification_subscriptions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            endpoint TEXT NOT NULL,
            p256dh VARCHAR(255),
            auth VARCHAR(255),
            user_agent VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        "CREATE INDEX IF NOT EXISTS ix_notif_subs_user ON notification_subscriptions (user_id)",
        """CREATE TABLE IF NOT EXISTS notification_preferences (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            category VARCHAR(20) NOT NULL,
            enabled BOOLEAN DEFAULT TRUE,
            CONSTRAINT uq_notif_pref_user_category UNIQUE (user_id, category)
        )""",
    ]
    # Each ALTER/CREATE runs inside its own SAVEPOINT on a SHARED connection.
    # Per-statement transactions kept opening fresh pooler connections (NullPool),
    # which Supabase rate-limits → "server closed connection unexpectedly". Using
    # a single connection + nested transactions (SAVEPOINT) preserves error
    # isolation (rollback to savepoint on failure) without exhausting the pool.
    import logging as _logging
    log = _logging.getLogger(__name__)
    with remote_engine.connect() as c:
        for s in stmts:
            sp = c.begin()
            try:
                c.execute(_text(s))
                sp.commit()
            except Exception as _e:
                sp.rollback()
                log.warning("migration stmt failed: %s", _e)

    _migrate_kitchen_id_integrity()

    # Record migrations as applied (idempotent — ON CONFLICT DO NOTHING).
    # These represent the cumulative state of `_online_migrate()` ALTER lists,
    # mapped to the phase they were introduced in.
    db_record_migration("001_initial",                    "Baseline schema (all tables prior to Phase 0)")
    db_record_migration("002_kitchen_id_integrity",       "NOT NULL kitchen_id on operational tables")
    db_record_migration("003_audit_log_expansion",        "Phase 0 — event_category + before/after_value")
    db_record_migration("004_schema_migrations_registry", "Phase 0 — versioned migration tracking")

    # Phase 1 — backfill schools.json → schools table on first run.
    _backfill_schools_from_json()
    db_record_migration("005_schools_master",             "Phase 1 — schools + school_classes tables")
    db_record_migration("006_suppliers_master",           "Phase 1 — suppliers + items.default_supplier_id")
    db_record_migration("007_menu_approval_workflow",     "Phase 2 — saved_menus.status + target_date + approval fields")
    db_record_migration("008_student_requests",           "Phase 2 — student_requests table")
    db_record_migration("009_purchase_orders",            "Phase 3 — purchase_orders + po_lines tables")
    db_record_migration("010_receiving_inspections",      "Phase 3 — inspections + signoffs + lines + disputes tables")
    db_record_migration("011_items_po_linkage",           "Phase 3 — items.parent_po_line_id + inspection_line_id + storage_routing")
    db_record_migration("012_production_batches",         "Phase 4 — production_batches + batch_consumed_items + food_samples")
    db_record_migration("013_distribution_layer",         "Phase 5 — delivery_confirmations + leftovers + vehicles + drivers")
    db_record_migration("014_finance_module",             "Phase 6 — expenses + volunteer_payments + lra_periods")
    db_record_migration("015_aslap_daily_ops",            "Phase 7 — daily_checklists + water_quality + observations + comms + weekly reports")
    db_record_migration("016_notifications",              "Phase 8 — notifications + subscriptions + preferences")


# Tables where kitchen_id MUST be set (operational data scoped to a kitchen).
# NOT in this list (kitchen_id stays nullable by design):
#   - food_prices, food_prices_history → NULL = global TKPI default shared across kitchens
#   - audit_log → login/system events legitimately have no kitchen context
_KITCHEN_SCOPED_TABLES = ("items", "trays", "tray_items", "print_jobs", "scan_errors")


def _migrate_kitchen_id_integrity():
    """Backfill NULL kitchen_id rows + apply NOT NULL constraint.

    Idempotent. Multi-tenant safe:
      - If exactly 1 active kitchen exists in the DB, NULL rows are backfilled to that kitchen.
      - If 2+ active kitchens exist, NULLs are LEFT UNTOUCHED (ambiguous; ops must resolve manually).
      - NOT NULL is only applied to a column once it has zero NULLs, so partial state is safe.

    Why this matters: any insert path that bypasses the FastAPI backend (e.g., a
    standalone scanner client writing direct to Supabase) and forgets to set
    kitchen_id will silently produce orphaned rows that don't show in the UI.
    Applying NOT NULL at the DB layer turns that silent failure into a hard error.
    """
    from sqlalchemy import text as _text
    import logging
    log = logging.getLogger(__name__)

    with remote_engine.begin() as c:
        n_active = c.execute(_text("SELECT count(*) FROM kitchens WHERE active = true")).scalar() or 0
        sole_kid = None
        if n_active == 1:
            sole_kid = c.execute(_text("SELECT id FROM kitchens WHERE active = true")).scalar()

        for tbl in _KITCHEN_SCOPED_TABLES:
            try:
                n_null = c.execute(_text(
                    f"SELECT count(*) FROM {tbl} WHERE kitchen_id IS NULL"
                )).scalar() or 0
            except Exception as e:
                log.debug("kitchen_id audit skipped for %s: %s", tbl, e)
                continue

            if n_null > 0:
                if sole_kid is not None:
                    c.execute(
                        _text(f"UPDATE {tbl} SET kitchen_id = :kid WHERE kitchen_id IS NULL"),
                        {"kid": sole_kid},
                    )
                    log.info("backfilled %d NULL kitchen_id rows in %s -> kitchen %d",
                             n_null, tbl, sole_kid)
                else:
                    log.warning(
                        "%s has %d NULL kitchen_id rows but %d active kitchens exist; "
                        "skipping backfill (requires manual ops decision)",
                        tbl, n_null, n_active,
                    )
                    continue

            # Re-check post-backfill before constraining.
            remaining = c.execute(_text(
                f"SELECT count(*) FROM {tbl} WHERE kitchen_id IS NULL"
            )).scalar() or 0
            if remaining == 0:
                try:
                    c.execute(_text(f"ALTER TABLE {tbl} ALTER COLUMN kitchen_id SET NOT NULL"))
                except Exception as e:
                    # Already NOT NULL → idempotent no-op; only warn on real errors.
                    msg = str(e).lower()
                    if "already" not in msg and "not null" not in msg:
                        log.warning("could not enforce NOT NULL on %s.kitchen_id: %s", tbl, e)


# ── Phase 1 — schools.json → schools table backfill ─────────────────────────

# Map raw `age_group` strings from schools.json to a coarse `level` enum.
def _infer_level_from_age_group(age_group: str) -> str:
    s = (age_group or "").upper()
    if s.startswith("PAUD"):
        return "PAUD"
    if s.startswith("TK") or "KB" in s:
        return "TK"
    if s.startswith("SD"):
        return "SD"
    if s.startswith("SMP") or s.startswith("MTS"):
        return "SMP"
    if s.startswith("SMA") or s.startswith("MA"):
        return "SMA"
    return "SD"  # safe default — most binaan are SD-aged


def _backfill_schools_from_json() -> None:
    """One-shot: import data/schools.json into the schools table on first run.

    Safe to call repeatedly: only inserts when the schools table for kitchen 1
    (the bootstrap kitchen) is empty AND the JSON file exists.

    Multi-tenant note: existing JSON has no kitchen_id, so we attribute every
    legacy row to the bootstrap kitchen (id=1, "DPMBG Paseh"). Operators can
    re-assign rows manually via the admin UI after migration.
    """
    import json as _json
    import logging
    from sqlalchemy import text as _text

    log = logging.getLogger(__name__)
    if not remote_engine:
        return

    schools_json_path = os.path.join(
        os.path.dirname(os.path.dirname(BASE_DIR)),  # repo root
        "data", "schools.json",
    )
    # BASE_DIR = backend/, dirname twice = repo root, then data/schools.json
    if not os.path.isfile(schools_json_path):
        # Try relative to backend dir parent (more common deployment layout)
        alt = os.path.join(os.path.dirname(BASE_DIR), "data", "schools.json")
        if os.path.isfile(alt):
            schools_json_path = alt
        else:
            return  # nothing to backfill

    with remote_engine.connect() as c:
        existing = c.execute(_text(
            "SELECT count(*) FROM schools WHERE kitchen_id = 1"
        )).scalar() or 0
        bootstrap_kitchen = c.execute(_text(
            "SELECT id FROM kitchens WHERE id = 1"
        )).first()

    if existing > 0:
        return  # already backfilled
    if bootstrap_kitchen is None:
        log.warning("schools backfill skipped: kitchen id=1 not found")
        return

    try:
        with open(schools_json_path, "r", encoding="utf-8") as f:
            rows = _json.load(f)
    except Exception as e:
        log.warning("schools backfill skipped: cannot read %s: %s", schools_json_path, e)
        return

    inserted = 0
    with remote_engine.begin() as c:
        for r in rows:
            try:
                age_group = str(r.get("age_group") or "SD (7-9 tahun)")
                c.execute(remote_schools.insert().values(
                    kitchen_id=1,
                    name=str(r.get("name") or "Sekolah Tanpa Nama")[:150],
                    level=_infer_level_from_age_group(age_group),
                    age_group=age_group[:50],
                    student_count=int(r.get("student_count") or 0),
                    distance=int(r.get("distance") or 0),
                    legacy_school_id=int(r.get("school_id") or 0) or None,
                    is_active=True,
                ))
                inserted += 1
            except Exception as e:
                log.warning("schools backfill row failed (%s): %s", r.get("name"), e)
    if inserted:
        log.info("schools backfill: inserted %d rows for kitchen id=1", inserted)


# ── Phase 1 — kitchen-scoped queries for schools / suppliers ────────────────

def db_list_schools(kitchen_id: int, active_only: bool = True) -> list[dict]:
    """Return schools for a kitchen as a list of dicts compatible with the
    legacy schools.json shape used by `_scan_allocations` / `_compute_deliveries`.
    Adds new fields (level, age_group, gps, contact) on top.
    """
    if not remote_engine:
        return []
    with remote_engine.connect() as c:
        q = select(remote_schools).where(remote_schools.c.kitchen_id == kitchen_id)
        if active_only:
            q = q.where(remote_schools.c.is_active.is_(True))
        rows = c.execute(q.order_by(remote_schools.c.distance, remote_schools.c.id)).all()
    out = []
    for r in rows:
        out.append({
            "id":               r.id,
            "school_id":        r.legacy_school_id or r.id,  # legacy callsites read this
            "name":             r.name,
            "address":          r.address,
            "level":            r.level,
            "age_group":        r.age_group,
            "student_count":    int(r.student_count or 0),
            "distance":         int(r.distance or 0),
            "gps_lat":          r.gps_lat,
            "gps_long":         r.gps_long,
            "contact":          r.contact,
            "is_active":        bool(r.is_active),
            "created_at":       r.created_at.isoformat() if r.created_at else None,
        })
    return out


def db_get_school(school_id: int, kitchen_id: int) -> Optional[dict]:
    if not remote_engine:
        return None
    with remote_engine.connect() as c:
        r = c.execute(
            select(remote_schools).where(
                (remote_schools.c.id == school_id) &
                (remote_schools.c.kitchen_id == kitchen_id)
            )
        ).first()
    if not r:
        return None
    return {
        "id":               r.id,
        "school_id":        r.legacy_school_id or r.id,
        "name":             r.name,
        "address":          r.address,
        "level":            r.level,
        "age_group":        r.age_group,
        "student_count":    int(r.student_count or 0),
        "distance":         int(r.distance or 0),
        "gps_lat":          r.gps_lat,
        "gps_long":         r.gps_long,
        "contact":          r.contact,
        "is_active":        bool(r.is_active),
        "created_at":       r.created_at.isoformat() if r.created_at else None,
    }


def db_list_suppliers(kitchen_id: int, active_only: bool = True) -> list[dict]:
    if not remote_engine:
        return []
    with remote_engine.connect() as c:
        q = select(remote_suppliers).where(remote_suppliers.c.kitchen_id == kitchen_id)
        if active_only:
            q = q.where(remote_suppliers.c.is_active.is_(True))
        rows = c.execute(q.order_by(remote_suppliers.c.name, remote_suppliers.c.id)).all()
    return [
        {
            "id":         r.id,
            "name":       r.name,
            "contact":    r.contact,
            "npwp":       r.npwp,
            "rekening":   r.rekening,
            "bank_name":  r.bank_name,
            "kategori":   r.kategori,
            "rating":     int(r.rating or 0),
            "notes":      r.notes,
            "is_active":  bool(r.is_active),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


# ── Phase 3 — Purchase Orders + Inspections + Disputes helpers ────────────

def db_list_purchase_orders(
    kitchen_id: int,
    status: Optional[str] = None,
    supplier_id: Optional[int] = None,
) -> list[dict]:
    if not remote_engine:
        return []
    with remote_engine.connect() as c:
        q = select(remote_purchase_orders).where(remote_purchase_orders.c.kitchen_id == kitchen_id)
        if status:
            q = q.where(remote_purchase_orders.c.status == status)
        if supplier_id:
            q = q.where(remote_purchase_orders.c.supplier_id == supplier_id)
        rows = c.execute(q.order_by(remote_purchase_orders.c.created_at.desc())).all()
    return [dict(r._mapping) | {
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "expected_delivery_date": str(r.expected_delivery_date) if r.expected_delivery_date else None,
        "sent_at": r.sent_at.isoformat() if r.sent_at else None,
        "received_at": r.received_at.isoformat() if r.received_at else None,
    } for r in rows]


def db_get_purchase_order(po_id: int, kitchen_id: int) -> Optional[dict]:
    if not remote_engine:
        return None
    with remote_engine.connect() as c:
        po = c.execute(
            select(remote_purchase_orders).where(
                (remote_purchase_orders.c.id == po_id) &
                (remote_purchase_orders.c.kitchen_id == kitchen_id)
            )
        ).first()
        if not po:
            return None
        lines = c.execute(
            select(remote_po_lines).where(remote_po_lines.c.po_id == po_id)
            .order_by(remote_po_lines.c.id)
        ).all()

    out = dict(po._mapping)
    out["created_at"] = po.created_at.isoformat() if po.created_at else None
    out["expected_delivery_date"] = str(po.expected_delivery_date) if po.expected_delivery_date else None
    out["sent_at"] = po.sent_at.isoformat() if po.sent_at else None
    out["received_at"] = po.received_at.isoformat() if po.received_at else None
    out["lines"] = [dict(l._mapping) for l in lines]
    return out


def db_list_inspections(
    kitchen_id: int,
    status: Optional[str] = None,
) -> list[dict]:
    if not remote_engine:
        return []
    with remote_engine.connect() as c:
        q = select(remote_receiving_inspections).where(
            remote_receiving_inspections.c.kitchen_id == kitchen_id
        )
        if status:
            q = q.where(remote_receiving_inspections.c.status == status)
        rows = c.execute(q.order_by(remote_receiving_inspections.c.created_at.desc())).all()
    return [dict(r._mapping) | {
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
    } for r in rows]


def db_get_inspection(inspection_id: int, kitchen_id: int) -> Optional[dict]:
    if not remote_engine:
        return None
    with remote_engine.connect() as c:
        row = c.execute(
            select(remote_receiving_inspections).where(
                (remote_receiving_inspections.c.id == inspection_id) &
                (remote_receiving_inspections.c.kitchen_id == kitchen_id)
            )
        ).first()
        if not row:
            return None
        lines = c.execute(
            select(remote_inspection_lines).where(remote_inspection_lines.c.inspection_id == inspection_id)
            .order_by(remote_inspection_lines.c.id)
        ).all()
        signoffs = c.execute(
            select(remote_inspection_signoffs).where(remote_inspection_signoffs.c.inspection_id == inspection_id)
            .order_by(remote_inspection_signoffs.c.signed_at)
        ).all()

    out = dict(row._mapping)
    out["created_at"] = row.created_at.isoformat() if row.created_at else None
    out["completed_at"] = row.completed_at.isoformat() if row.completed_at else None
    out["lines"] = [dict(l._mapping) | {
        "created_at": l.created_at.isoformat() if l.created_at else None,
    } for l in lines]
    out["signoffs"] = [dict(s._mapping) | {
        "signed_at": s.signed_at.isoformat() if s.signed_at else None,
    } for s in signoffs]
    return out


def db_list_supplier_disputes(kitchen_id: int, status: Optional[str] = None) -> list[dict]:
    if not remote_engine:
        return []
    with remote_engine.connect() as c:
        q = select(remote_supplier_disputes).where(remote_supplier_disputes.c.kitchen_id == kitchen_id)
        if status:
            q = q.where(remote_supplier_disputes.c.status == status)
        rows = c.execute(q.order_by(remote_supplier_disputes.c.created_at.desc())).all()
    return [dict(r._mapping) | {
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
    } for r in rows]


def db_get_supplier(supplier_id: int, kitchen_id: int) -> Optional[dict]:
    if not remote_engine:
        return None
    with remote_engine.connect() as c:
        r = c.execute(
            select(remote_suppliers).where(
                (remote_suppliers.c.id == supplier_id) &
                (remote_suppliers.c.kitchen_id == kitchen_id)
            )
        ).first()
    if not r:
        return None
    return {
        "id":         r.id,
        "name":       r.name,
        "contact":    r.contact,
        "npwp":       r.npwp,
        "rekening":   r.rekening,
        "bank_name":  r.bank_name,
        "kategori":   r.kategori,
        "rating":     int(r.rating or 0),
        "notes":      r.notes,
        "is_active":  bool(r.is_active),
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


# Inferred event_category from action prefix when caller doesn't pass one.
# Keeps existing call sites working without forcing per-call category.
_ACTION_CATEGORY_PREFIXES = {
    "login":        "auth",
    "logout":       "auth",
    "user":         "auth",
    "menu":         "menu",
    "saved_menu":   "menu",
    "items":        "receiving",
    "item":         "receiving",
    "defect":       "receiving",
    "inspection":   "receiving",
    "school":       "compliance",   # master data
    "supplier":     "finance",      # master data, owned by accountant
    "po":           "finance",
    "purchase_order": "finance",
    "expense":      "finance",
    "lra":          "finance",
    "finance":      "finance",
    "volunteer":    "finance",
    "signoff":      "compliance",
    "dispute":      "compliance",
    "container":    "receiving",
    "scan":         "production",
    "production":   "production",
    "batch":        "production",
    "tray":         "production",
    "delivery":     "distribution",
    "distribution": "distribution",
    "price":        "finance",
    "po":           "finance",
    "expense":      "finance",
    "lra":          "finance",
    "checklist":    "compliance",
    "audit":        "compliance",
    "water":        "compliance",
    "observation":  "production",
    "comm":         "compliance",
    "aslap":        "compliance",
}


def _infer_event_category(action: str) -> str | None:
    if not action:
        return None
    head = action.split(".", 1)[0].lower()
    return _ACTION_CATEGORY_PREFIXES.get(head, "system")


def db_audit_log(
    action: str,
    user_id: int | None = None,
    kitchen_id: int | None = None,
    org_id: int | None = None,
    target_type: str | None = None,
    target_id: str | int | None = None,
    ip_address: str | None = None,
    details: dict | None = None,
    event_category: str | None = None,
    before_value: dict | list | None = None,
    after_value: dict | list | None = None,
) -> None:
    """Insert an audit log entry. Best-effort: failures are logged but don't raise.

    Phase 0 fields:
      event_category — high-level grouping (auto-inferred from action if omitted)
      before_value   — JSON snapshot before an update/delete (for compliance "from-to")
      after_value    — JSON snapshot after a create/update
    """
    import json as _json
    import logging
    if not remote_engine:
        return
    category = (event_category or _infer_event_category(action) or "")[:30] or None
    try:
        with remote_engine.begin() as c:
            c.execute(remote_audit_log.insert().values(
                action=action[:80],
                event_category=category,
                user_id=user_id,
                kitchen_id=kitchen_id,
                org_id=org_id,
                target_type=(target_type or "")[:50] or None,
                target_id=str(target_id)[:100] if target_id is not None else None,
                before_value=_json.dumps(before_value, ensure_ascii=False, default=str)[:4000] if before_value is not None else None,
                after_value=_json.dumps(after_value, ensure_ascii=False, default=str)[:4000] if after_value is not None else None,
                ip_address=(ip_address or "")[:45] or None,
                details=_json.dumps(details, ensure_ascii=False, default=str)[:4000] if details else None,
            ))
    except Exception as e:
        logging.getLogger(__name__).warning("audit_log write failed: %s", e)


# ── Phase 8 — notification helpers ────────────────────────────────────────

VALID_NOTIF_CATEGORIES = ("menu", "receiving", "production", "distribution", "finance", "compliance", "system")


def db_create_notification(
    user_id: int,
    type: str,
    title: str,
    *,
    category: str = "system",
    body: str | None = None,
    payload: dict | None = None,
    link: str | None = None,
    kitchen_id: int | None = None,
) -> int | None:
    """Best-effort: insert a notification row, return id (or None on failure).
    Respects user opt-out via notification_preferences (silently skip).
    """
    if not remote_engine:
        return None
    import json as _json
    import logging
    log = logging.getLogger(__name__)
    try:
        with remote_engine.connect() as c:
            # Check preference: user can disable a whole category.
            row = c.execute(
                select(remote_notification_preferences.c.enabled).where(
                    (remote_notification_preferences.c.user_id == user_id) &
                    (remote_notification_preferences.c.category == category)
                )
            ).first()
            if row and row.enabled is False:
                return None

        with remote_engine.begin() as c:
            res = c.execute(
                remote_notifications.insert().values(
                    user_id=user_id,
                    kitchen_id=kitchen_id,
                    type=type[:50],
                    category=(category if category in VALID_NOTIF_CATEGORIES else "system")[:20],
                    title=title[:150],
                    body=body,
                    payload_json=_json.dumps(payload, ensure_ascii=False, default=str)[:4000] if payload else None,
                    link=(link or "")[:255] or None,
                ).returning(remote_notifications.c.id)
            )
            return res.scalar()
    except Exception as e:
        log.warning("notification create failed: %s", e)
        return None


def db_notify_users_with_perm(perm: str, kitchen_id: int, **notif_kwargs) -> list[int]:
    """Find users who hold `perm` for `kitchen_id`, send each a notification.
    Returns list of created notification ids.
    """
    from sqlalchemy import text as _text
    from backend.utils.permissions import ROLE_PERMS
    if not remote_engine:
        return []

    # Find candidate users via user_kitchens for this kitchen + global super/platform admins.
    with remote_engine.connect() as c:
        rows = c.execute(_text("""
            SELECT DISTINCT u.id, u.role, uk.role AS kitchen_role
            FROM users u
            LEFT JOIN user_kitchens uk ON uk.user_id = u.id AND uk.kitchen_id = :kid
            WHERE u.role IN ('platform_admin', 'superadmin', 'admin') OR uk.kitchen_id = :kid
        """), {"kid": kitchen_id}).fetchall()

    notif_ids: list[int] = []
    for r in rows:
        # Build a fake user dict that has_permission can evaluate.
        u = {"id": r.id, "role": r.role, "org_id": None}
        # has_permission needs to look up kitchen role too — we mock via direct ROLE_PERMS lookup
        # for the kitchen_role we already have.
        granted = False
        if r.role in ("platform_admin", "superadmin", "admin"):
            granted = True
        elif r.kitchen_role:
            perms = ROLE_PERMS.get(r.kitchen_role, set())
            granted = perm in perms
        if not granted:
            continue
        nid = db_create_notification(user_id=r.id, kitchen_id=kitchen_id, **notif_kwargs)
        if nid:
            notif_ids.append(nid)
    return notif_ids


def db_record_migration(version: str, description: str | None = None) -> None:
    """Record that a versioned migration has been applied. Idempotent.

    Used by Phase 0+ migration framework to track ordered schema changes
    beyond the catch-all `_online_migrate()` ALTER TABLE list.
    """
    if not remote_engine:
        return
    import logging
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    try:
        with remote_engine.begin() as c:
            stmt = pg_insert(remote_schema_migrations).values(
                version=version[:50],
                description=(description or "")[:255] or None,
            ).on_conflict_do_nothing(index_elements=["version"])
            c.execute(stmt)
    except Exception as e:
        logging.getLogger(__name__).warning("schema_migrations write failed: %s", e)


def db_list_applied_migrations() -> list[dict]:
    """Return all applied migrations, ordered by version."""
    if not remote_engine:
        return []
    with remote_engine.connect() as c:
        rows = c.execute(
            select(
                remote_schema_migrations.c.version,
                remote_schema_migrations.c.applied_at,
                remote_schema_migrations.c.description,
            ).order_by(remote_schema_migrations.c.version)
        ).all()
    return [
        {"version": r.version, "applied_at": r.applied_at.isoformat() if r.applied_at else None, "description": r.description}
        for r in rows
    ]


def db_list_nutrition_overrides(kitchen_id: int) -> dict[str, dict]:
    """Return {food_code: overrides_dict} for the given kitchen."""
    import json as _json
    with engine.connect() as c:
        rows = c.execute(
            select(
                remote_food_nutrition_overrides.c.food_code,
                remote_food_nutrition_overrides.c.overrides,
            ).where(remote_food_nutrition_overrides.c.kitchen_id == kitchen_id)
        ).all()
    out: dict[str, dict] = {}
    for r in rows:
        try:
            out[r.food_code] = _json.loads(r.overrides) if r.overrides else {}
        except Exception:
            out[r.food_code] = {}
    return out


def db_upsert_nutrition_override(
    kitchen_id: int, food_code: str, overrides: dict, user_id: Optional[int]
) -> None:
    import json as _json
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    stmt = pg_insert(remote_food_nutrition_overrides).values(
        kitchen_id=kitchen_id,
        food_code=food_code,
        overrides=_json.dumps(overrides),
        updated_by=user_id,
        updated_at=datetime.now(),
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_nutr_override_kitchen_code",
        set_={
            "overrides": stmt.excluded.overrides,
            "updated_by": stmt.excluded.updated_by,
            "updated_at": stmt.excluded.updated_at,
        },
    )
    with engine.begin() as c:
        c.execute(stmt)


def db_delete_nutrition_override(kitchen_id: int, food_code: str) -> int:
    with engine.begin() as c:
        res = c.execute(
            remote_food_nutrition_overrides.delete().where(
                (remote_food_nutrition_overrides.c.kitchen_id == kitchen_id) &
                (remote_food_nutrition_overrides.c.food_code == food_code)
            )
        )
        return res.rowcount


def db_log_price_change(
    kitchen_id: Optional[int], food_code: str,
    price: Optional[int], manual_price: Optional[int],
    source: str, user_id: Optional[int],
) -> None:
    with engine.begin() as c:
        c.execute(remote_food_prices_history.insert().values(
            kitchen_id=kitchen_id,
            food_code=food_code,
            price=price,
            manual_price=manual_price,
            source=source,
            changed_by=user_id,
        ))


def db_list_saved_menus(
    kitchen_id: int,
    status: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> list[dict]:
    """Return saved menus for a kitchen, newest first, without payload.

    Phase 2 filters: status (draft/pending_review/approved/locked/archived/rejected)
    and target_date range.
    """
    with engine.connect() as c:
        q = select(
            remote_saved_menus.c.id,
            remote_saved_menus.c.name,
            remote_saved_menus.c.created_by,
            remote_saved_menus.c.created_at,
            remote_saved_menus.c.status,
            remote_saved_menus.c.source,
            remote_saved_menus.c.target_date,
            remote_saved_menus.c.target_school_id,
            remote_saved_menus.c.submitted_at,
            remote_saved_menus.c.approved_at,
            remote_saved_menus.c.approved_by,
            remote_saved_menus.c.review_notes,
            remote_users.c.username.label("created_by_username"),
        ).select_from(
            remote_saved_menus.outerjoin(
                remote_users,
                remote_saved_menus.c.created_by == remote_users.c.id,
            )
        ).where(remote_saved_menus.c.kitchen_id == kitchen_id)

        if status:
            q = q.where(remote_saved_menus.c.status == status)
        if from_date:
            q = q.where(remote_saved_menus.c.target_date >= from_date)
        if to_date:
            q = q.where(remote_saved_menus.c.target_date <= to_date)

        rows = c.execute(q.order_by(remote_saved_menus.c.created_at.desc())).all()

    return [
        {
            "id": r.id,
            "name": r.name,
            "created_by": r.created_by,
            "created_by_username": r.created_by_username or str(r.created_by),
            "created_at": str(r.created_at),
            "status": r.status or "draft",
            "source": r.source or "optimizer",
            "target_date": str(r.target_date) if r.target_date else None,
            "target_school_id": r.target_school_id,
            "submitted_at": str(r.submitted_at) if r.submitted_at else None,
            "approved_at": str(r.approved_at) if r.approved_at else None,
            "approved_by": r.approved_by,
            "review_notes": r.review_notes,
        }
        for r in rows
    ]


def db_save_menu(
    kitchen_id: int,
    name: str,
    created_by: int,
    payload_dict: dict,
    *,
    source: str = "optimizer",
    target_date: Optional[str] = None,
    target_school_id: Optional[int] = None,
) -> dict:
    """Insert a new saved menu row. New menus start in 'draft' status.

    Phase 2: source ('optimizer' from forward solver, 'manual' from reverse-mode
    Build Menu Manual UI), and optional target_date / target_school_id for
    cycle-check + forecast generation.
    """
    import json as _json
    with engine.begin() as c:
        res = c.execute(
            remote_saved_menus.insert().values(
                kitchen_id=kitchen_id,
                name=name,
                created_by=created_by,
                payload=_json.dumps(payload_dict),
                status="draft",
                source=source,
                target_date=target_date,
                target_school_id=target_school_id,
            ).returning(
                remote_saved_menus.c.id,
                remote_saved_menus.c.created_at,
            )
        )
        row = res.first()
    return {
        "id": row.id,
        "name": name,
        "created_at": str(row.created_at),
        "status": "draft",
        "source": source,
        "target_date": target_date,
        "target_school_id": target_school_id,
    }


# ── Phase 2 — approval state machine + cycle check + forecast ──────────────

# Allowed transitions. Anything not listed is a 400.
_MENU_TRANSITIONS = {
    "submit":  [("draft", "pending_review"), ("rejected", "pending_review")],
    "approve": [("pending_review", "approved")],
    "reject":  [("pending_review", "rejected")],
    "lock":    [("approved", "locked")],
    "archive": [("approved", "archived"), ("locked", "archived"), ("draft", "archived"), ("rejected", "archived")],
    "revert_to_draft": [("rejected", "draft"), ("pending_review", "draft")],
}


def db_menu_transition(
    kitchen_id: int,
    menu_id: int,
    action: str,
    user_id: int,
    notes: Optional[str] = None,
) -> Optional[dict]:
    """Apply an approval state transition. Returns updated menu dict or None
    if the menu doesn't exist. Raises ValueError if transition is invalid.
    """
    from sqlalchemy import text as _text
    if action not in _MENU_TRANSITIONS:
        raise ValueError(f"Unknown action: {action}")
    valid_from = [pair[0] for pair in _MENU_TRANSITIONS[action]]

    with engine.begin() as c:
        row = c.execute(
            select(remote_saved_menus.c.id, remote_saved_menus.c.status)
            .where(
                (remote_saved_menus.c.id == menu_id) &
                (remote_saved_menus.c.kitchen_id == kitchen_id)
            )
        ).first()
        if not row:
            return None
        current = row.status or "draft"
        if current not in valid_from:
            raise ValueError(f"Cannot {action} from status '{current}'. Valid from: {valid_from}")
        new_status = next(t for f, t in _MENU_TRANSITIONS[action] if f == current)

        values: dict = {"status": new_status}
        from datetime import datetime as _dt
        now = _dt.now()
        if action == "submit":
            values["submitted_at"] = now
            values["submitted_by"] = user_id
            # Clear prior reject notes when re-submitting
            if current == "rejected":
                values["review_notes"] = None
        elif action == "approve":
            values["approved_at"] = now
            values["approved_by"] = user_id
            if notes is not None:
                values["review_notes"] = notes
        elif action == "reject":
            values["review_notes"] = notes or ""
        elif action == "revert_to_draft":
            values["submitted_at"] = None
            values["submitted_by"] = None
            values["approved_at"] = None
            values["approved_by"] = None

        c.execute(
            remote_saved_menus.update()
            .where(remote_saved_menus.c.id == menu_id)
            .values(**values)
        )

    # Return the fresh menu (without payload) for the caller.
    menus = db_list_saved_menus(kitchen_id)
    return next((m for m in menus if m["id"] == menu_id), None)


def db_menu_cycle_check(kitchen_id: int, days: int = 20) -> dict:
    """Analyze the last `days` days of approved/locked menus for BGN siklus 20
    compliance: in 20 days, telur ≤ 8x, ayam ≤ 8x, tahu ≤ 10x, tempe ≤ 10x.

    Returns {bahan_count: {keyword: int}, warnings: [str], menus_analyzed: int}.
    """
    import json as _json
    from datetime import date as _date, timedelta as _td

    if not remote_engine:
        return {"bahan_count": {}, "warnings": [], "menus_analyzed": 0}

    cutoff = (_date.today() - _td(days=days)).isoformat()

    with remote_engine.connect() as c:
        rows = c.execute(
            select(remote_saved_menus.c.id, remote_saved_menus.c.payload, remote_saved_menus.c.target_date)
            .where(
                (remote_saved_menus.c.kitchen_id == kitchen_id) &
                (remote_saved_menus.c.status.in_(["approved", "locked"])) &
                (
                    (remote_saved_menus.c.target_date.is_(None)) |
                    (remote_saved_menus.c.target_date >= cutoff)
                )
            )
        ).all()

    # Define BGN-aligned bahan keywords + max counts in 20-day window.
    LIMITS = {
        "telur":  8,
        "ayam":   8,
        "tahu":  10,
        "tempe": 10,
        "ikan":   8,
        "daging sapi": 4,
    }

    bahan_count: dict[str, int] = {k: 0 for k in LIMITS}
    menus_analyzed = 0

    for r in rows:
        try:
            payload = _json.loads(r.payload) if r.payload else {}
        except Exception:
            continue
        menus_analyzed += 1
        # Search payload for bahan names — handles both forward-optimizer shape
        # (week[].items[].name) and manual mode (items[].name).
        names: list[str] = []
        if isinstance(payload, dict):
            if isinstance(payload.get("week"), list):
                for day in payload["week"]:
                    for it in day.get("items", []) if isinstance(day, dict) else []:
                        n = (it or {}).get("name")
                        if n: names.append(n)
            if isinstance(payload.get("items"), list):
                for it in payload["items"]:
                    n = (it or {}).get("name")
                    if n: names.append(n)
            if isinstance(payload.get("groups"), list):
                for g in payload["groups"]:
                    if isinstance(g, dict) and isinstance(g.get("week"), list):
                        for day in g["week"]:
                            for it in day.get("items", []) if isinstance(day, dict) else []:
                                n = (it or {}).get("name")
                                if n: names.append(n)
        for n in names:
            low = n.lower()
            for kw in LIMITS:
                if kw in low:
                    bahan_count[kw] += 1

    warnings: list[str] = []
    for kw, limit in LIMITS.items():
        if bahan_count[kw] > limit:
            warnings.append(
                f"{kw.title()} muncul {bahan_count[kw]}x dalam {days} hari (max {limit}x menurut siklus BGN)"
            )

    return {
        "days": days,
        "menus_analyzed": menus_analyzed,
        "limits": LIMITS,
        "bahan_count": bahan_count,
        "warnings": warnings,
    }


def db_menu_forecast(
    kitchen_id: int,
    from_date: str,
    to_date: str,
    school_id: Optional[int] = None,
) -> dict:
    """Sum bahan needs from approved/locked menus in [from_date, to_date].

    Math: per menu, total grams of bahan X = sum(item.grams for item with name~X)
                                            × (target school's student_count
                                               or sum of all active schools')
    Returns {bahan: {grams_total, est_cost_idr}, total_cost_idr, schools_in_scope}
    """
    import json as _json

    if not remote_engine:
        return {"bahan": {}, "total_cost_idr": 0, "schools_in_scope": []}

    # Resolve student-count multiplier.
    schools = db_list_schools(kitchen_id)
    if school_id:
        schools = [s for s in schools if s["id"] == school_id]
    total_students = sum(s.get("student_count", 0) for s in schools) or 1

    with remote_engine.connect() as c:
        rows = c.execute(
            select(remote_saved_menus.c.id, remote_saved_menus.c.payload, remote_saved_menus.c.target_date,
                   remote_saved_menus.c.target_school_id, remote_saved_menus.c.name)
            .where(
                (remote_saved_menus.c.kitchen_id == kitchen_id) &
                (remote_saved_menus.c.status.in_(["approved", "locked"])) &
                (remote_saved_menus.c.target_date >= from_date) &
                (remote_saved_menus.c.target_date <= to_date)
            )
        ).all()

    bahan: dict[str, dict] = {}

    for r in rows:
        try:
            payload = _json.loads(r.payload) if r.payload else {}
        except Exception:
            continue

        # Multiplier: if menu targets a specific school, only that school's
        # student count; else multiply by all schools in scope (filtered above).
        if r.target_school_id and not school_id:
            menu_students = next(
                (s["student_count"] for s in schools if s["id"] == r.target_school_id),
                0,
            )
        else:
            menu_students = total_students

        # Collect items from all known payload shapes.
        items: list[dict] = []
        if isinstance(payload, dict):
            if isinstance(payload.get("items"), list):
                items.extend(payload["items"])
            if isinstance(payload.get("week"), list):
                for day in payload["week"]:
                    if isinstance(day, dict):
                        items.extend(day.get("items") or [])
            if isinstance(payload.get("groups"), list):
                for g in payload["groups"]:
                    if isinstance(g, dict) and isinstance(g.get("week"), list):
                        for day in g["week"]:
                            if isinstance(day, dict):
                                items.extend(day.get("items") or [])

        for it in items:
            if not isinstance(it, dict):
                continue
            name = it.get("name") or it.get("code") or "(unknown)"
            grams_per_porsi = float(it.get("grams") or 0)
            cost_per_porsi = float(it.get("cost") or 0)
            grams_total = grams_per_porsi * menu_students
            cost_total = cost_per_porsi * menu_students

            entry = bahan.setdefault(name, {
                "grams_total": 0.0,
                "est_cost_idr": 0.0,
                "appearances": 0,
                "code": it.get("code"),
                "category": it.get("category"),
            })
            entry["grams_total"] += grams_total
            entry["est_cost_idr"] += cost_total
            entry["appearances"] += 1

    # Round numeric fields.
    for k, v in bahan.items():
        v["grams_total"] = round(v["grams_total"], 1)
        v["est_cost_idr"] = round(v["est_cost_idr"])

    return {
        "from_date": from_date,
        "to_date": to_date,
        "schools_in_scope": [{"id": s["id"], "name": s["name"], "student_count": s["student_count"]} for s in schools],
        "total_students": total_students,
        "menus_analyzed": len(rows),
        "bahan": bahan,
        "total_cost_idr": round(sum(v["est_cost_idr"] for v in bahan.values())),
    }


def db_get_saved_menu(kitchen_id: int, menu_id: int) -> Optional[dict]:
    """Return a single saved menu row (including payload) or None."""
    import json as _json
    with engine.connect() as c:
        row = c.execute(
            select(remote_saved_menus).where(
                (remote_saved_menus.c.id == menu_id) &
                (remote_saved_menus.c.kitchen_id == kitchen_id)
            )
        ).first()
    if not row:
        return None
    d = dict(row._mapping)
    try:
        d["payload"] = _json.loads(d["payload"]) if d["payload"] else {}
    except Exception:
        d["payload"] = {}
    d["created_at"] = str(d["created_at"])
    return d


def db_delete_saved_menu(kitchen_id: int, menu_id: int) -> int:
    """Delete a saved menu scoped to kitchen. Returns rowcount."""
    with engine.begin() as c:
        res = c.execute(
            remote_saved_menus.delete().where(
                (remote_saved_menus.c.id == menu_id) &
                (remote_saved_menus.c.kitchen_id == kitchen_id)
            )
        )
        return res.rowcount


def db_get_nutrition_daily(kitchen_id: int, date_str: str) -> dict:
    """Return aggregate nutrition for a given date from items received that day.

    Steps:
    1. Count delivered trays for the date.
    2. Load ingredient items received that day.
    3. Match item names against TKPI via load_tkpi_all (without price filter).
    4. Sum nutrients per item (weight_grams / 100 * nutrient_per_100g).
    5. Distribute evenly across schools by student_count.
    6. Compare against AKG preset for SD (7-9 tahun) as default.
    """
    import json as _json
    from datetime import date as _date
    from sqlalchemy import text as _text
    import os

    with engine.connect() as c:
        trays_delivered = c.execute(_text("""
            SELECT COUNT(*) FROM trays
            WHERE created_date_delivery = :d AND delivery = true AND kitchen_id = :kid
        """), {"d": date_str, "kid": kitchen_id}).scalar() or 0

    if trays_delivered == 0:
        zero = {"energy": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}
        return {
            "date": date_str, "trays_delivered": 0, "schools": [],
            "totals": dict(zero), "per_student": dict(zero),
            "compliance_pct": dict(zero), "totals_pct_met": dict(zero),
            "akg_target": dict(zero), "no_data": True,
        }

    with engine.connect() as c:
        item_rows = c.execute(_text("""
            SELECT name, weight_grams FROM items
            WHERE created_date_receiving = :d AND kitchen_id = :kid AND weight_grams IS NOT NULL
        """), {"d": date_str, "kid": kitchen_id}).fetchall()

    # Build TKPI lookup by name (lowercase) — load raw CSV without price filter
    _TKPI_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "data", "tkpi.csv",
    )
    tkpi_by_name: dict = {}
    if os.path.isfile(_TKPI_PATH):
        import csv as _csv, re as _re
        def _sf(v):
            if not v or str(v).strip() in ("", "-", "Tr", "tr", "NA", "na"): return 0.0
            try: return float(_re.sub(r"[^\d.\-]", "", str(v).strip()))
            except: return 0.0
        with open(_TKPI_PATH, "r", encoding="utf-8-sig") as f:
            for row in _csv.DictReader(f):
                n = (row.get("NAMA BAHAN") or "").strip().lower()
                if n:
                    tkpi_by_name[n] = {
                        "energy":  _sf(row.get("ENERGI")),
                        "protein": _sf(row.get("PROTEIN")),
                        "fat":     _sf(row.get("LEMAK")),
                        "carbs":   _sf(row.get("KH")),
                    }

    # Sum nutrients from all items received that day
    total_nutr = {"energy": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}
    for item in item_rows:
        name_key = (item.name or "").strip().lower()
        tkpi = tkpi_by_name.get(name_key)
        if not tkpi:
            continue
        w = float(item.weight_grams or 0)
        for k in total_nutr:
            total_nutr[k] += w / 100.0 * tkpi[k]

    # Per-tray nutrition (one tray = one student)
    per_tray = {k: total_nutr[k] / trays_delivered for k in total_nutr} if trays_delivered else {k: 0.0 for k in total_nutr}

    # Load schools
    _SCHOOLS_FILE = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "data", "schools.json",
    )
    schools_raw = []
    if os.path.isfile(_SCHOOLS_FILE):
        with open(_SCHOOLS_FILE, "r", encoding="utf-8") as f:
            schools_raw = _json.load(f)

    # AKG full-day targets per age group (Permenkes 28/2019)
    AKG_FULL_DAY_BY_GROUP = {
        "TK (4-6 tahun)":  {"energy": 1350.0, "protein": 25.0, "fat": 62.0, "carbs": 215.0},
        "SD (7-9 tahun)":  {"energy": 1650.0, "protein": 40.0, "fat": 65.0, "carbs": 250.0},
        "SD (10-12 tahun)":{"energy": 2000.0, "protein": 50.0, "fat": 80.0, "carbs": 300.0},
        "SMP (13-15 tahun)":{"energy": 2400.0, "protein": 70.0, "fat": 80.0, "carbs": 350.0},
        "SMA (16-18 tahun)":{"energy": 2500.0, "protein": 65.0, "fat": 85.0, "carbs": 400.0},
    }
    DEFAULT_AKG = AKG_FULL_DAY_BY_GROUP["SD (7-9 tahun)"]

    school_rows = []
    grand = {"energy": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}
    grand_target = {"energy": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}
    for s in schools_raw:
        sc = int(s.get("student_count", 0))
        akg = AKG_FULL_DAY_BY_GROUP.get(s.get("age_group"), DEFAULT_AKG)
        nutr = {k: round(per_tray[k] * sc, 2) for k in per_tray}
        pct = {k: round(nutr[k] / (akg[k] * sc) * 100, 1) if akg[k] * sc > 0 else 0.0 for k in nutr}
        school_rows.append({
            "school_id": int(s.get("school_id", 0)),
            "school_name": s.get("name", ""),
            "age_group": s.get("age_group", "SD (7-9 tahun)"),
            "student_count": sc,
            "nutrition": nutr,
            "akg_target": {k: round(akg[k] * sc, 2) for k in akg},
            "pct_met": pct,
        })
        for k in grand:
            grand[k] += nutr[k]
            grand_target[k] += akg[k] * sc

    total_students = sum(int(s.get("student_count", 0)) for s in schools_raw)
    grand_pct = {k: round(grand[k] / grand_target[k] * 100, 1) if grand_target[k] > 0 else 0.0 for k in grand}

    per_student = {k: round(grand[k] / total_students, 2) if total_students > 0 else 0.0 for k in grand}
    return {
        "date": date_str,
        "trays_delivered": trays_delivered,
        "schools": school_rows,
        "totals": {k: round(grand[k], 2) for k in grand},
        "per_student": per_student,
        "compliance_pct": grand_pct,
        "totals_pct_met": grand_pct,
        "akg_target": {k: round(grand_target[k], 2) for k in grand_target},
        "no_data": False,
    }


def db_get_nutrition_weekly(kitchen_id: int, from_str: str, to_str: str) -> list[dict]:
    """Return daily nutrition + AKG compliance for each day from_str..to_str (inclusive)."""
    from datetime import date as _date, timedelta as _td
    d = _date.fromisoformat(from_str)
    end = _date.fromisoformat(to_str)
    results = []
    while d <= end:
        day_data = db_get_nutrition_daily(kitchen_id, str(d))
        if day_data.get("no_data"):
            results.append({"date": str(d), "no_data": True, "color": "no_data", "pct_met_avg": None, "schools": []})
        else:
            pct = day_data.get("totals_pct_met", {})
            vals = [v for v in pct.values() if v is not None]
            avg_pct = round(sum(vals) / len(vals), 1) if vals else 0.0
            color = "green" if avg_pct >= 90 else "amber" if avg_pct >= 70 else "red"
            results.append({
                "date": str(d),
                "no_data": False,
                "color": color,
                "pct_met_avg": avg_pct,
                "totals": day_data.get("totals", {}),
                "totals_pct_met": pct,
                "schools": day_data.get("schools", []),
            })
        d += _td(days=1)
    return results


def db_get_price_history(kitchen_id: int, food_code: str, limit: int = 50) -> list[dict]:
    with engine.connect() as c:
        rows = c.execute(
            select(remote_food_prices_history)
            .where(
                (remote_food_prices_history.c.food_code == food_code) &
                ((remote_food_prices_history.c.kitchen_id == kitchen_id) |
                 (remote_food_prices_history.c.kitchen_id.is_(None)))
            )
            .order_by(remote_food_prices_history.c.changed_at.desc())
            .limit(limit)
        ).all()
    return [dict(r._mapping) for r in rows]

# ============================================================
# HELPERS
# ============================================================

def _iso_now() -> str:
    return now_local_iso()

# ---------- Local scan queue ----------

def local_enqueue_scan(code: str, step: str, label: str) -> None:
    with local_engine.begin() as c:
        c.execute(local_scan_queue.insert().values(
            code=code,
            step=step,
            label=label,
            created_at=_iso_now(),
            synced=0,
        ))

def local_enqueue_error(code: str, step: str, reason: str) -> None:
    with local_engine.begin() as c:
        c.execute(local_scan_errors.insert().values(
            code=code,
            step=step,
            created_at=_iso_now(),
            reason=reason,
            synced=0,
        ))

# ---------- Remote helpers ----------

def db_insert_item(item_id: str, name: str, weight_g: int, unit: str = "g",
                   reason: Optional[str] = None, kitchen_id: Optional[int] = None) -> None:
    """Insert a new ingredient with receiving=True."""
    with engine.begin() as c:
        c.execute(remote_items.insert().values(
            id=item_id,
            kitchen_id=kitchen_id,
            name=name,
            weight_grams=weight_g,
            unit=unit,
            reason=reason,
            receiving=True,
            created_at_receiving=datetime.now(),
            created_date_receiving=date.today(),
        ))

def db_get_item_availability(item_id: str, kitchen_id: int) -> Optional[dict]:
    """Return original weight + already-defected total + available remainder.

    Returns None if the item doesn't exist or belongs to a different kitchen.
    Used by the defect endpoint for over-allocation validation and by the
    receiving picker to show "X g available from Y g".
    """
    from sqlalchemy import text as _text
    with engine.connect() as c:
        row = c.execute(_text("""
            SELECT i.id, i.name, i.weight_grams, i.unit, i.kitchen_id,
                   i.created_date_receiving,
                   COALESCE(SUM(d.weight_grams), 0) AS already_defected
            FROM items i
            LEFT JOIN defect_items d ON d.item_id = i.id
            WHERE i.id = :id
            GROUP BY i.id, i.name, i.weight_grams, i.unit, i.kitchen_id, i.created_date_receiving
        """), {"id": item_id}).first()
    if not row or row.kitchen_id != kitchen_id:
        return None
    original = int(row.weight_grams or 0)
    defected = int(row.already_defected or 0)
    return {
        "id": row.id,
        "name": row.name,
        "unit": row.unit,
        "original_weight_grams": original,
        "already_defected_grams": defected,
        "available_grams": max(0, original - defected),
        "created_date_receiving": str(row.created_date_receiving) if row.created_date_receiving else None,
    }


def db_register_tray(tray_id: str, kitchen_id: Optional[int] = None) -> None:
    """Register a new tray if not exists (scoped by kitchen)."""
    with engine.begin() as c:
        exists = c.execute(
            select(remote_trays.c.tray_id).where(
                (remote_trays.c.tray_id == tray_id) &
                (remote_trays.c.kitchen_id == kitchen_id)
            )
        ).first()
        if not exists:
            c.execute(remote_trays.insert().values(tray_id=tray_id, kitchen_id=kitchen_id))

def db_enqueue_print(tspl: str, kitchen_id: Optional[int] = None) -> int:
    with engine.begin() as c:
        res = c.execute(remote_print_jobs.insert().values(tspl=tspl, kitchen_id=kitchen_id))
        pk = res.inserted_primary_key
        return int(pk[0]) if pk and pk[0] is not None else -1

def db_fetch_next_print_job(kitchen_id: Optional[int] = None) -> Optional[dict]:
    with engine.connect() as c:
        q = select(remote_print_jobs).where(remote_print_jobs.c.printed == 0)
        if kitchen_id is not None:
            q = q.where(remote_print_jobs.c.kitchen_id == kitchen_id)
        row = c.execute(q.order_by(remote_print_jobs.c.id.asc()).limit(1)).first()
        return dict(row._mapping) if row else None

def db_mark_printed(job_id: int) -> None:
    with engine.begin() as c:
        c.execute(
            remote_print_jobs.update()
            .where(remote_print_jobs.c.id == job_id)
            .values(printed=1, printed_at=func.now())
        )

# ---------- Food prices ----------

def db_upsert_food_price(food_code: str, food_name: str, price_per_100g: int,
                         source: str = "sayurbox", kitchen_id: Optional[int] = None) -> None:
    """Insert or update a food price by (TKPI code, kitchen)."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    with engine.begin() as c:
        stmt = pg_insert(remote_food_prices).values(
            kitchen_id=kitchen_id,
            food_code=food_code,
            food_name=food_name,
            price_per_100g=price_per_100g,
            source=source,
            scraped_at=datetime.now(),
            updated_at=datetime.now(),
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_food_prices_code_kitchen",
            set_={
                "food_name": stmt.excluded.food_name,
                "price_per_100g": stmt.excluded.price_per_100g,
                "source": stmt.excluded.source,
                "scraped_at": stmt.excluded.scraped_at,
                "updated_at": stmt.excluded.updated_at,
            }
        )
        c.execute(stmt)


def db_get_food_prices(kitchen_id: Optional[int] = None) -> dict[str, int]:
    """Return food prices as {food_code: effective_price_per_100g}.

    Priority order (highest wins):
      1. kitchen-specific manual_price (accountant override for this kitchen)
      2. kitchen-specific scraped price_per_100g
      3. global manual_price (rarely used)
      4. global scraped price_per_100g
    """
    def _eff(r) -> int:
        return r.manual_price if r.manual_price is not None else r.price_per_100g

    with engine.connect() as c:
        if kitchen_id is None:
            rows = c.execute(
                select(
                    remote_food_prices.c.food_code,
                    remote_food_prices.c.price_per_100g,
                    remote_food_prices.c.manual_price,
                ).where(remote_food_prices.c.kitchen_id.is_(None))
            ).all()
            return {r.food_code: _eff(r) for r in rows}

        rows = c.execute(
            select(
                remote_food_prices.c.food_code,
                remote_food_prices.c.price_per_100g,
                remote_food_prices.c.manual_price,
                remote_food_prices.c.kitchen_id,
            ).where(
                (remote_food_prices.c.kitchen_id == kitchen_id) |
                (remote_food_prices.c.kitchen_id.is_(None))
            )
        ).all()
        prices: dict[str, int] = {}
        # globals first
        for r in rows:
            if r.kitchen_id is None:
                prices[r.food_code] = _eff(r)
        # then override with kitchen-specific
        for r in rows:
            if r.kitchen_id == kitchen_id:
                prices[r.food_code] = _eff(r)
        return prices


def db_get_price_scrape_status(kitchen_id: Optional[int] = None) -> list[dict]:
    """Return food_prices rows for status display (optionally scoped by kitchen)."""
    with engine.connect() as c:
        q = select(remote_food_prices)
        if kitchen_id is not None:
            q = q.where(
                (remote_food_prices.c.kitchen_id == kitchen_id) |
                (remote_food_prices.c.kitchen_id.is_(None))
            )
        rows = c.execute(q.order_by(remote_food_prices.c.scraped_at.desc())).all()
        return [dict(r._mapping) for r in rows]


# ---------- Organizations ----------

def db_list_organizations(active_only: bool = True) -> list[dict]:
    with engine.connect() as c:
        q = select(remote_organizations)
        if active_only:
            q = q.where(remote_organizations.c.active.is_(True))
        rows = c.execute(q.order_by(remote_organizations.c.id)).all()
        return [dict(r._mapping) for r in rows]


def db_get_organization(org_id: int) -> Optional[dict]:
    with engine.connect() as c:
        row = c.execute(
            select(remote_organizations).where(remote_organizations.c.id == org_id)
        ).first()
        return dict(row._mapping) if row else None


# ---------- Kitchens ----------

def db_list_kitchens(active_only: bool = True, org_id: Optional[int] = None) -> list[dict]:
    with engine.connect() as c:
        q = select(remote_kitchens)
        if active_only:
            q = q.where(remote_kitchens.c.active.is_(True))
        if org_id is not None:
            q = q.where(remote_kitchens.c.org_id == org_id)
        rows = c.execute(q.order_by(remote_kitchens.c.id)).all()
        return [dict(r._mapping) for r in rows]


def db_get_kitchen(kitchen_id: int) -> Optional[dict]:
    with engine.connect() as c:
        row = c.execute(
            select(remote_kitchens).where(remote_kitchens.c.id == kitchen_id)
        ).first()
        return dict(row._mapping) if row else None


def db_get_kitchen_by_scanner_key(key: str) -> Optional[dict]:
    if not key:
        return None
    with engine.connect() as c:
        row = c.execute(
            select(remote_kitchens).where(
                (remote_kitchens.c.scanner_key == key) &
                (remote_kitchens.c.active.is_(True))
            )
        ).first()
        return dict(row._mapping) if row else None


def db_get_kitchen_by_print_key(key: str) -> Optional[dict]:
    if not key:
        return None
    with engine.connect() as c:
        row = c.execute(
            select(remote_kitchens).where(
                (remote_kitchens.c.cloud_print_key == key) &
                (remote_kitchens.c.active.is_(True))
            )
        ).first()
        return dict(row._mapping) if row else None


def db_list_user_kitchens(user_id: int) -> list[dict]:
    """Return the kitchens a user can access, with per-kitchen role."""
    with engine.connect() as c:
        rows = c.execute(
            select(
                remote_kitchens.c.id,
                remote_kitchens.c.slug,
                remote_kitchens.c.name,
                remote_kitchens.c.label_title,
                remote_user_kitchens.c.role,
            ).select_from(
                remote_user_kitchens.join(
                    remote_kitchens,
                    remote_user_kitchens.c.kitchen_id == remote_kitchens.c.id,
                )
            ).where(
                (remote_user_kitchens.c.user_id == user_id) &
                (remote_kitchens.c.active.is_(True))
            ).order_by(remote_kitchens.c.id)
        ).all()
        return [dict(r._mapping) for r in rows]