"""Role → permission mapping for per-kitchen roles.

Role hierarchy (Phase 0 — 7-role RBAC):

  Global (users.role):
    platform_admin  — cross-org operator (implicit superadmin for every org)
    superadmin      — per-org, implicit admin for every kitchen in its org
    user            — per-kitchen role lives in `user_kitchens.role`

  Per-kitchen (user_kitchens.role) — 5 BGN-aligned roles:
    head_sppg     — Kepala SPPG (pimpinan, approve menu, sign LRA, full kitchen ops)
    nutritionist  — Ahli Gizi (menu planner, AKG, QC bahan, joint inspection sign-off)
    accountant    — Akuntan (PO, expense, LRA, joint inspection sign-off)
    aslap         — Asisten Lapangan (daily checklist, delivery confirm, joint inspection sign-off)
    head_kitchen  — Kepala Chef (production batch trigger, tablet processing scan)

  Legacy / backward-compat aliases (still accepted, mapped to new perms):
    admin     → head_sppg   (kitchens with single op manager)
    ahli_gizi → nutritionist (renamed for BGN terminology)

  Deprecated (no new assignment, no current user):
    kitchen_staff — fallback role from early prototype, no role-specific perms.

superadmin and platform_admin both receive the union of every permission when
calling has_permission.

Phase 0 introduces the role identifiers and minimal permission sets. Permissions
for features that don't exist yet (joint inspection sign-off, menu approval,
LRA generation, etc.) will be added per phase as endpoints land.
"""
from typing import Iterable, Set

from fastapi import Depends, HTTPException
from sqlalchemy import select

from backend.core.database import engine, remote_user_kitchens


# ── Permission definitions ──────────────────────────────────────────────────
# Strings, not enums, so they're trivially serialisable to JSON for the UI.

# head_sppg = full kitchen ops, includes admin powers + future approval perms.
HEAD_SPPG_PERMS: Set[str] = {
    "dashboard.view",
    "notification.view",
    "notification.subscribe",
    "executive.kpi_view",

    "items.view",
    "items.create",
    "items.edit",
    "trays.view",
    "menu.view",
    "menu.optimize",
    "menu.scrape",
    "menu.save",
    "foods.edit",
    "scan_errors.view",
    "export.daily",
    "export.range",
    "prices.override",
    "prices.history",
    "reports.variance",
    "nutrition.report",
    "admin.kitchens",
    "admin.users",
    # Phase 1
    "school.manage",
    "school.view",
    "supplier.manage",
    "supplier.view",
    # Phase 2 — approval workflow + cycle/forecast read
    "menu.approve",
    "menu.lock",
    "menu.cycle_check",
    "menu.forecast",
    "menu.calc",
    "student_request.view",
    "student_request.resolve",
    # Phase 3 — Joint Inspection (head_sppg oversees + can act in any role for tiny SPPGs)
    "po.view",
    "po.create",
    "po.edit",
    "po.delete",
    "inspection.view",
    "inspection.create",
    "inspection.signoff_quality",
    "inspection.signoff_quantity",
    "inspection.signoff_physical",
    "inspection.reject_bahan",
    "inspection.finalize",
    "container.split",
    "dispute.view",
    "dispute.resolve",
    # Phase 4 — Production tracking + tablet Processing scan + QC + sample retention
    "production.view",
    "production.start_batch",
    "production.end_batch",
    "production.processing_scan",
    "production.qc_approve",
    "sample.view",
    "sample.manage",
    # Phase 5 — Distribution oversight (head_sppg sees all)
    "distribution.view",
    "distribution.dispatch",
    "distribution.leftover",
    "vehicle.manage",
    "driver.manage",
    # Phase 6 — head_sppg signs LRA (final step before submit ke BGN)
    "finance.view",
    "finance.price_trends",
    "expense.view",
    "expense.create",
    "expense.edit",
    "volunteer.manage",
    "lra.view",
    "lra.generate",
    "lra.signoff",
    # Phase 9 — head_sppg compliance bundle export
    "compliance.bundle_export",
    # Phase 7 — head_sppg supervises ASLAP daily ops + signs weekly report
    "checklist.view",
    "checklist.template_manage",
    "water_quality.view",
    "production_observation.view",
    "school_comm_log.view",
    "aslap_report.view",
    "aslap_report.signoff",
}

# nutritionist = menu planner + nutrition + future QC bahan / sign-off.
NUTRITIONIST_PERMS: Set[str] = {
    "dashboard.view",
    "notification.view",
    "notification.subscribe",
    "executive.kpi_view",

    "items.view",
    "trays.view",
    "menu.view",
    "menu.optimize",
    "menu.scrape",
    "menu.save",
    "foods.edit",
    "nutrition.report",
    # Phase 1 — read-only access to master data so menu plans can hit schools.
    "school.view",
    "supplier.view",
    # Phase 2 — Reverse Optimizer + submit menu for approval
    "menu.calc",
    "menu.build_manual",
    "menu.submit_for_review",
    "menu.cycle_check",
    "menu.forecast",
    "student_request.view",
    "student_request.create",
    "student_request.resolve",
    # Phase 3 — Joint Inspection (Ahli Gizi = quality sign-off + reject authority)
    "inspection.view",
    "inspection.signoff_quality",
    "inspection.reject_bahan",
    "po.view",
    "dispute.view",
    # Phase 4 — Ahli Gizi punya QC approve authority sebelum pemorsian + sample retention
    "production.view",
    "production.qc_approve",
    "sample.view",
    "sample.manage",
    # Phase 5 — Ahli Gizi sees distribution status (gizi compliance audit)
    "distribution.view",
    # Phase 6 — Ahli Gizi liat price trends (untuk decide menu cheapest opsi)
    "finance.price_trends",
}

# accountant = finance + reporting + price + future PO / LRA / sign-off.
ACCOUNTANT_PERMS: Set[str] = {
    "dashboard.view",
    "notification.view",
    "notification.subscribe",
    "executive.kpi_view",

    "items.view",
    "trays.view",
    "menu.view",
    "prices.override",
    "prices.history",
    "reports.variance",
    "scan_errors.view",
    "export.daily",
    "export.range",
    # Phase 1
    "supplier.manage",
    "supplier.view",
    "school.view",
    # Phase 2 — read-only menu workflow visibility (for cost forecast in Phase 6)
    "menu.cycle_check",
    "menu.forecast",
    # Phase 3 — Akuntan owns PO + does quantity sign-off
    "po.view",
    "po.create",
    "po.edit",
    "po.delete",
    "inspection.view",
    "inspection.signoff_quantity",
    "dispute.view",
    "dispute.resolve",
    # Phase 5 — Akuntan owns vehicle/driver master (operational expense)
    "vehicle.manage",
    "driver.manage",
    "distribution.view",
    # Phase 9 — Akuntan also exports compliance bundle (signs LRA part)
    "compliance.bundle_export",
    # Phase 6 — Akuntan = primary finance owner
    "finance.view",
    "finance.price_trends",
    "expense.view",
    "expense.create",
    "expense.edit",
    "volunteer.manage",
    "lra.view",
    "lra.generate",
}

# aslap = field operations enforcer. Daily checklist, receiving (Joint Inspection),
# delivery confirm, scan errors. Read-mostly except for create/observe.
ASLAP_PERMS: Set[str] = {
    "dashboard.view",
    "notification.view",
    "notification.subscribe",
    "executive.kpi_view",

    "items.view",
    "items.create",
    "trays.view",
    "scan_errors.view",
    "reports.variance",
    # Phase 1 — needs to see schools (for distribution) and suppliers (for receiving)
    "school.view",
    "supplier.view",
    # Phase 2 — ASLAP juga bisa capture request siswa langsung di lapangan
    "student_request.view",
    "student_request.create",
    # Phase 3 — ASLAP runs the joint inspection: opens session, physical sign-off, container split
    "po.view",
    "inspection.view",
    "inspection.create",
    "inspection.signoff_physical",
    "inspection.finalize",
    "container.split",
    "dispute.view",
    # Phase 4 — ASLAP observes production + sees samples
    "production.view",
    "sample.view",
    # Phase 5 — ASLAP runs distribution: dispatch + leftover log + receipt monitor
    "distribution.view",
    "distribution.dispatch",
    "distribution.leftover",
    # Phase 7 — ASLAP daily ops core
    "checklist.view",
    "checklist.daily",
    "water_quality.view",
    "water_quality.log",
    "production_observation.view",
    "production_observation.create",
    "school_comm_log.view",
    "school_comm_log.create",
    "aslap_report.view",
    "aslap_report.generate",
}

# head_kitchen = production lead. Read menu, edit items (mark processed via
# tablet scan), view trays. Triggers production batch (Phase 4).
HEAD_KITCHEN_PERMS: Set[str] = {
    "dashboard.view",
    "notification.view",
    "notification.subscribe",
    "executive.kpi_view",

    "items.view",
    "items.edit",
    "trays.view",
    "menu.view",
    "scan_errors.view",
    # Phase 1 — needs to know which school each batch is for during production
    "school.view",
    # Phase 4 — Kepala Chef = production batch trigger + tablet Processing scan
    "production.view",
    "production.start_batch",
    "production.end_batch",
    "production.processing_scan",
    "sample.view",
}

ROLE_PERMS: dict = {
    # New BGN-aligned role identifiers (Phase 0+)
    "head_sppg":    HEAD_SPPG_PERMS,
    "nutritionist": NUTRITIONIST_PERMS,
    "accountant":   ACCOUNTANT_PERMS,
    "aslap":        ASLAP_PERMS,
    "head_kitchen": HEAD_KITCHEN_PERMS,
    # Backward-compat aliases — same perms, accepted for legacy users / scripts.
    "admin":        HEAD_SPPG_PERMS,
    "ahli_gizi":    NUTRITIONIST_PERMS,
}

ALL_PERMS: Set[str] = set().union(*ROLE_PERMS.values())

# Canonical per-kitchen role identifiers (excludes legacy aliases).
# Used by the admin UI as the recommended role list when assigning new users.
CANONICAL_KITCHEN_ROLES: tuple = (
    "head_sppg",
    "nutritionist",
    "accountant",
    "aslap",
    "head_kitchen",
)

# Valid role identifiers for input validation. Includes legacy aliases so
# existing assignments and seed scripts keep working through Phase 0.
VALID_KITCHEN_ROLES: tuple = tuple(ROLE_PERMS.keys())

# Canonical alias map — UI may resolve legacy → canonical for display.
ROLE_ALIASES: dict = {
    "admin":     "head_sppg",
    "ahli_gizi": "nutritionist",
}

# Roles that confer admin-tier kitchen management (used by kitchen_admin_ids
# query). `head_sppg` inherits the legacy `admin` role's full kitchen ops.
KITCHEN_MANAGER_ROLES: tuple = ("head_sppg", "admin")


# ── Resolution ──────────────────────────────────────────────────────────────

def is_platform_admin(user: dict) -> bool:
    return user.get("role") == "platform_admin"


def is_org_superadmin(user: dict) -> bool:
    # legacy "admin" global role kept for the bootstrap DPMBG user
    return user.get("role") in ("superadmin", "admin")


def _kitchen_role_for(user_id: int, kitchen_id: int) -> str | None:
    """Look up a user's role in a specific kitchen."""
    with engine.connect() as c:
        row = c.execute(
            select(remote_user_kitchens.c.role)
            .where(
                (remote_user_kitchens.c.user_id == user_id) &
                (remote_user_kitchens.c.kitchen_id == kitchen_id)
            )
        ).first()
        return row.role if row else None


def kitchen_admin_ids(user_id: int) -> Set[int]:
    """Return the set of kitchen_ids where `user_id` holds a kitchen-manager
    role (`head_sppg` or legacy `admin`). Used to grant scoped kitchen
    management to kitchen-level managers.
    """
    with engine.connect() as c:
        rows = c.execute(
            select(remote_user_kitchens.c.kitchen_id)
            .where(
                (remote_user_kitchens.c.user_id == user_id) &
                (remote_user_kitchens.c.role.in_(KITCHEN_MANAGER_ROLES))
            )
        ).all()
    return {r.kitchen_id for r in rows}


def is_kitchen_admin_of(user: dict, kitchen_id: int) -> bool:
    return kitchen_id in kitchen_admin_ids(user["id"])


def permissions_for(user: dict, kitchen_id: int | None = None) -> Set[str]:
    """Return the permission set for `user` acting on `kitchen_id`.

    platform_admin and org superadmin always get ALL_PERMS (they are trusted
    above the per-kitchen tier). Regular `user` roles are looked up in
    user_kitchens for the target kitchen.
    """
    if is_platform_admin(user) or is_org_superadmin(user):
        return ALL_PERMS

    if kitchen_id is None:
        return set()

    role = _kitchen_role_for(user["id"], kitchen_id)
    if role is None:
        return set()
    return ROLE_PERMS.get(role, set())


def has_permission(user: dict, perm: str, kitchen_id: int | None = None) -> bool:
    return perm in permissions_for(user, kitchen_id=kitchen_id)


# ── FastAPI dependency ─────────────────────────────────────────────────────

def require_permission(perm: str):
    """Usage:
        @router.post("/items", dependencies=[Depends(require_permission("items.create"))])
    The dependency re-resolves kitchen from request context (header/JWT) via
    get_current_kitchen, so permission is always evaluated against the kitchen
    the request is acting on.
    """
    from backend.utils.auth import get_current_user, get_current_kitchen

    def checker(
        user: dict = Depends(get_current_user),
        kitchen: dict = Depends(get_current_kitchen),
    ):
        if not has_permission(user, perm, kitchen_id=kitchen["id"]):
            raise HTTPException(status_code=403, detail=f"Missing permission: {perm}")
        return kitchen

    return checker


def require_any_permission(perms: Iterable[str]):
    """Allow any one of the listed permissions."""
    from backend.utils.auth import get_current_user, get_current_kitchen
    perms = tuple(perms)

    def checker(
        user: dict = Depends(get_current_user),
        kitchen: dict = Depends(get_current_kitchen),
    ):
        owned = permissions_for(user, kitchen_id=kitchen["id"])
        if not any(p in owned for p in perms):
            raise HTTPException(status_code=403, detail=f"Missing one of: {','.join(perms)}")
        return kitchen

    return checker
