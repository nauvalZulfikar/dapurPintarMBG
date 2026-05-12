"""Receiving Inspections — 3-sign-off Joint Inspection (Phase 3).

Cerita pagi yang ideal di SPPG Paseh:
- Jam 04:00 truk supplier datang.
- ASLAP buka tablet → POST /api/inspections (auto-loads PO line items as
  inspection_lines pending).
- 3 orang sign-off:
    - Ahli Gizi: POST /api/inspections/{id}/signoff (role='quality')
    - Akuntan : POST /api/inspections/{id}/signoff (role='quantity')
    - ASLAP   : POST /api/inspections/{id}/signoff (role='physical')
- Ahli Gizi reject specific line: POST .../lines/{line_id}/reject → dispute
  log + 0 label cetak for that line.
- ASLAP accept specific line: POST .../lines/{line_id}/accept with
  containers payload (manual split: 18 box × different weights). System
  generates N items rows + N barcode labels printed in one go.
- POST .../finalize closes the inspection (require all 3 signoffs OR partial
  if at least one line accepted).

Permissions:
  inspection.view            — all kitchen roles
  inspection.create          — head_sppg, accountant, aslap
  inspection.signoff_quality — nutritionist (head_sppg)
  inspection.signoff_quantity— accountant (head_sppg)
  inspection.signoff_physical— aslap (head_sppg)
  inspection.reject_bahan    — nutritionist (head_sppg) — line-level reject
  container.split            — head_sppg, aslap — accept line + multi-label print
  inspection.finalize        — head_sppg, aslap
"""
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from backend.core.database import (
    engine,
    remote_purchase_orders,
    remote_po_lines,
    remote_receiving_inspections,
    remote_inspection_lines,
    remote_inspection_signoffs,
    remote_supplier_disputes,
    remote_items,
    remote_suppliers,
    db_get_inspection, db_list_inspections,
    db_get_purchase_order,
    db_audit_log,
    db_notify_users_with_perm,
)
from backend.utils.auth import get_current_user
from backend.utils.permissions import require_permission, has_permission
from backend.utils.validators import new_item_id
from backend.services.printing import generate_label, create_and_push_job

router = APIRouter()

VALID_SIGNOFF_ROLES = ("quality", "quantity", "physical")
VALID_STORAGE_ROUTING = ("cook_immediate", "refrigerate", "freeze")
VALID_SEVERITY = ("low", "medium", "high")


class InspectionCreate(BaseModel):
    supplier_id: Optional[int] = None
    po_id:       Optional[int] = None
    notes:       Optional[str] = None


class SignoffBody(BaseModel):
    role:            str = Field(..., max_length=20)         # quality | quantity | physical
    status:          str = Field("approved", max_length=20)  # approved | rejected
    notes:           Optional[str] = None
    photo_path:      Optional[str] = None
    is_offline_sign: bool = False


class ContainerIn(BaseModel):
    weight_grams: int = Field(..., gt=0)


class AcceptLineBody(BaseModel):
    containers:      list[ContainerIn] = Field(..., min_length=1)
    storage_routing: str = Field("refrigerate", max_length=20)
    notes:           Optional[str] = None


class RejectLineBody(BaseModel):
    reason:   str = Field(..., min_length=1)
    severity: str = Field("medium", max_length=20)
    photo_path: Optional[str] = None


# ── Inspection lifecycle ────────────────────────────────────────────────────


@router.get("/inspections")
async def list_inspections(
    status: Optional[str] = None,
    kitchen: dict = Depends(require_permission("inspection.view")),
):
    return {"inspections": db_list_inspections(kitchen["id"], status=status)}


@router.get("/inspections/{inspection_id}")
async def get_inspection(
    inspection_id: int,
    kitchen: dict = Depends(require_permission("inspection.view")),
):
    insp = db_get_inspection(inspection_id, kitchen["id"])
    if not insp:
        raise HTTPException(404, "Inspection tidak ditemukan.")
    return insp


@router.post("/inspections", status_code=201)
async def create_inspection(
    body: InspectionCreate,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("inspection.create")),
):
    """Open a new inspection session. If po_id given, auto-create one
    inspection_line per PO line (pending status).
    """
    supplier_id = body.supplier_id
    if body.po_id:
        po = db_get_purchase_order(body.po_id, kitchen["id"])
        if not po:
            raise HTTPException(404, "PO tidak ditemukan.")
        supplier_id = supplier_id or po.get("supplier_id")

    with engine.begin() as c:
        res = c.execute(
            remote_receiving_inspections.insert()
            .values(
                kitchen_id=kitchen["id"],
                supplier_id=supplier_id,
                po_id=body.po_id,
                status="inspecting",
                notes=body.notes,
                created_by=user.get("id"),
            )
            .returning(remote_receiving_inspections.c.id)
        )
        new_id = res.scalar()

        if body.po_id:
            # Auto-load lines from PO.
            po_lines = c.execute(
                select(remote_po_lines).where(remote_po_lines.c.po_id == body.po_id)
            ).all()
            for pl in po_lines:
                c.execute(
                    remote_inspection_lines.insert().values(
                        inspection_id=new_id,
                        po_line_id=pl.id,
                        item_name=pl.item_name,
                        expected_weight_grams=pl.total_weight_grams,
                        status="pending",
                    )
                )

    insp = db_get_inspection(new_id, kitchen["id"])
    db_audit_log(
        action="inspection.create",
        user_id=user.get("id"),
        kitchen_id=kitchen["id"],
        org_id=user.get("org_id"),
        target_type="inspection",
        target_id=str(new_id),
        after_value={"po_id": body.po_id, "supplier_id": supplier_id, "lines": len(insp.get("lines", []))},
    )
    # Phase 8 — notify 3 sign-off PICs (Ahli Gizi, Akuntan, ASLAP) that
    # truk dateng dan inspection sedang menunggu sign-off mereka.
    try:
        for perm in ("inspection.signoff_quality", "inspection.signoff_quantity", "inspection.signoff_physical"):
            db_notify_users_with_perm(
                perm=perm,
                kitchen_id=kitchen["id"],
                type="inspection.scheduled",
                category="receiving",
                title="Truk dateng — Joint Inspection sekarang",
                body=f"Inspeksi #{new_id} ({len(insp.get('lines', []))} line) butuh sign-off Anda.",
                link=f"/inspections",
                payload={"inspection_id": new_id, "po_id": body.po_id},
            )
    except Exception:
        pass
    return insp


# ── Sign-off (quality / quantity / physical) ────────────────────────────────


_SIGNOFF_PERM = {
    "quality":  "inspection.signoff_quality",
    "quantity": "inspection.signoff_quantity",
    "physical": "inspection.signoff_physical",
}


@router.post("/inspections/{inspection_id}/signoff")
async def submit_signoff(
    inspection_id: int,
    body: SignoffBody,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("inspection.view")),
):
    if body.role not in VALID_SIGNOFF_ROLES:
        raise HTTPException(400, f"Invalid role. Valid: {', '.join(VALID_SIGNOFF_ROLES)}")
    if body.status not in ("approved", "rejected"):
        raise HTTPException(400, "Status harus 'approved' atau 'rejected'.")

    perm_needed = _SIGNOFF_PERM[body.role]
    if not has_permission(user, perm_needed, kitchen_id=kitchen["id"]):
        raise HTTPException(403, f"Missing permission: {perm_needed}")

    insp = db_get_inspection(inspection_id, kitchen["id"])
    if not insp:
        raise HTTPException(404, "Inspection tidak ditemukan.")
    if insp.get("status") in ("accepted", "rejected", "closed"):
        raise HTTPException(400, f"Inspection sudah final (status={insp.get('status')}).")

    # 1 active sign-off per role per inspection. Re-submit overwrites previous.
    with engine.begin() as c:
        c.execute(
            remote_inspection_signoffs.delete().where(
                (remote_inspection_signoffs.c.inspection_id == inspection_id) &
                (remote_inspection_signoffs.c.role_required == body.role)
            )
        )
        c.execute(
            remote_inspection_signoffs.insert().values(
                inspection_id=inspection_id,
                role_required=body.role,
                user_id=user.get("id"),
                status=body.status,
                photo_path=body.photo_path,
                notes=body.notes,
                is_offline_sign=body.is_offline_sign,
            )
        )

    db_audit_log(
        action=f"inspection.signoff.{body.role}",
        user_id=user.get("id"),
        kitchen_id=kitchen["id"],
        org_id=user.get("org_id"),
        target_type="inspection",
        target_id=str(inspection_id),
        details={"status": body.status, "is_offline_sign": body.is_offline_sign},
    )
    return db_get_inspection(inspection_id, kitchen["id"])


# ── Per-line accept (container split + multi-label print) ───────────────────


def _new_unique_item_id() -> str:
    """Reuse the existing BHN-XXXXXXXX random format."""
    return new_item_id()


@router.post("/inspections/{inspection_id}/lines/{line_id}/accept")
async def accept_inspection_line(
    inspection_id: int,
    line_id: int,
    body: AcceptLineBody,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("container.split")),
):
    """ASLAP accepts a PO line: input N containers (manual weight per box) →
    generate N BHN-XXXXXXXX rows in items + N print jobs (multi-label).

    Math reuses existing receiving items table (each container = 1 row).
    Items are stamped with parent_po_line_id + inspection_line_id for audit.
    """
    if body.storage_routing not in VALID_STORAGE_ROUTING:
        raise HTTPException(400, f"Invalid storage_routing. Valid: {', '.join(VALID_STORAGE_ROUTING)}")

    insp = db_get_inspection(inspection_id, kitchen["id"])
    if not insp:
        raise HTTPException(404, "Inspection tidak ditemukan.")
    line = next((l for l in insp.get("lines", []) if l["id"] == line_id), None)
    if not line:
        raise HTTPException(404, "Line tidak ditemukan dalam inspeksi ini.")
    if line.get("status") in ("accepted", "rejected"):
        raise HTTPException(400, f"Line sudah final (status={line.get('status')}).")

    # Require at least quality + physical sign-offs as accepted before allowing accept.
    sign_status = {s["role_required"]: s["status"] for s in insp.get("signoffs", [])}
    missing = [r for r in ("quality", "physical") if sign_status.get(r) != "approved"]
    if missing:
        raise HTTPException(
            400,
            f"Belum ada sign-off approved dari: {', '.join(missing)}. "
            "Wajib Ahli Gizi (quality) + ASLAP (physical) approve dulu.",
        )

    actual_total = sum(c.weight_grams for c in body.containers)
    item_ids: list[str] = []
    today = date.today()

    with engine.begin() as c:
        # Update inspection line.
        c.execute(
            remote_inspection_lines.update()
            .where(remote_inspection_lines.c.id == line_id)
            .values(
                actual_weight_grams=actual_total,
                container_count=len(body.containers),
                storage_routing=body.storage_routing,
                status="accepted",
                notes=body.notes,
            )
        )
        # Insert N items rows (one per container).
        for cont in body.containers:
            item_id = _new_unique_item_id()
            item_ids.append(item_id)
            c.execute(
                remote_items.insert().values(
                    id=item_id,
                    kitchen_id=kitchen["id"],
                    name=line["item_name"],
                    weight_grams=cont.weight_grams,
                    unit="g",
                    receiving=True,
                    created_at_receiving=datetime.now(),
                    created_date_receiving=today,
                    parent_po_line_id=line.get("po_line_id"),
                    inspection_line_id=line_id,
                    storage_routing=body.storage_routing,
                )
            )

    # Multi-label print (one TSPL job per container) — same per-kitchen routing
    # used by the existing single-item flow.
    async def _print_all():
        for it_id, cont in zip(item_ids, body.containers):
            label = generate_label(it_id, line["item_name"], cont.weight_grams, kitchen=kitchen)
            try:
                await create_and_push_job(label, kitchen_id=kitchen["id"], printer_name=kitchen.get("printer_name"))
            except Exception:
                pass  # printing is best-effort; DB rows already committed

    background_tasks.add_task(_print_all)

    db_audit_log(
        action="container.split",
        user_id=user.get("id"),
        kitchen_id=kitchen["id"],
        org_id=user.get("org_id"),
        target_type="inspection_line",
        target_id=str(line_id),
        after_value={
            "containers": len(body.containers),
            "actual_total_g": actual_total,
            "expected_total_g": line.get("expected_weight_grams"),
            "item_ids": item_ids,
            "storage_routing": body.storage_routing,
        },
    )
    return {
        "ok": True,
        "inspection_line_id": line_id,
        "item_ids": item_ids,
        "containers_count": len(body.containers),
        "actual_weight_grams": actual_total,
        "labels_queued": len(item_ids),
    }


@router.post("/inspections/{inspection_id}/lines/{line_id}/reject")
async def reject_inspection_line(
    inspection_id: int,
    line_id: int,
    body: RejectLineBody,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("inspection.reject_bahan")),
):
    """Ahli Gizi reject specific line — bahan ditolak, NO label printed,
    inventory NOT increased, supplier_disputes row created.
    """
    if body.severity not in VALID_SEVERITY:
        raise HTTPException(400, f"Invalid severity. Valid: {', '.join(VALID_SEVERITY)}")

    insp = db_get_inspection(inspection_id, kitchen["id"])
    if not insp:
        raise HTTPException(404, "Inspection tidak ditemukan.")
    line = next((l for l in insp.get("lines", []) if l["id"] == line_id), None)
    if not line:
        raise HTTPException(404, "Line tidak ditemukan.")
    if line.get("status") in ("accepted", "rejected"):
        raise HTTPException(400, f"Line sudah final (status={line.get('status')}).")

    with engine.begin() as c:
        c.execute(
            remote_inspection_lines.update()
            .where(remote_inspection_lines.c.id == line_id)
            .values(status="rejected", notes=(body.reason or "")[:1000])
        )
        # Create dispute record.
        res = c.execute(
            remote_supplier_disputes.insert()
            .values(
                kitchen_id=kitchen["id"],
                supplier_id=insp.get("supplier_id"),
                inspection_id=inspection_id,
                inspection_line_id=line_id,
                item_name=line["item_name"],
                reason=body.reason,
                severity=body.severity,
                photo_path=body.photo_path,
                status="open",
                created_by=user.get("id"),
            )
            .returning(remote_supplier_disputes.c.id)
        )
        dispute_id = res.scalar()
        # Decrement supplier rating (cap at 1).
        if insp.get("supplier_id"):
            c.execute(
                remote_suppliers.update()
                .where(remote_suppliers.c.id == insp["supplier_id"])
                .values(rating=remote_suppliers.c.rating - 1)
            )

    db_audit_log(
        action="inspection.reject_bahan",
        user_id=user.get("id"),
        kitchen_id=kitchen["id"],
        org_id=user.get("org_id"),
        target_type="inspection_line",
        target_id=str(line_id),
        after_value={
            "dispute_id": dispute_id,
            "item_name": line["item_name"],
            "severity": body.severity,
            "supplier_id": insp.get("supplier_id"),
        },
    )
    return {"ok": True, "dispute_id": dispute_id, "inspection_line_id": line_id}


@router.post("/inspections/{inspection_id}/finalize")
async def finalize_inspection(
    inspection_id: int,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("inspection.finalize")),
):
    """Close the inspection. Final status:
      - 'accepted'  if all 3 sign-offs approved AND all lines accepted
      - 'rejected'  if any sign-off rejected OR all lines rejected
      - 'partial'   if mix of accepted + rejected lines
    """
    insp = db_get_inspection(inspection_id, kitchen["id"])
    if not insp:
        raise HTTPException(404, "Inspection tidak ditemukan.")
    if insp.get("status") in ("accepted", "rejected", "closed"):
        raise HTTPException(400, f"Inspection sudah final (status={insp.get('status')}).")

    sign_status = {s["role_required"]: s["status"] for s in insp.get("signoffs", [])}
    line_statuses = [l["status"] for l in insp.get("lines", [])]

    # Decision logic.
    any_signoff_rejected = "rejected" in sign_status.values()
    all_signoffs_approved = all(sign_status.get(r) == "approved" for r in VALID_SIGNOFF_ROLES)
    accepted_count = sum(1 for s in line_statuses if s == "accepted")
    rejected_count = sum(1 for s in line_statuses if s == "rejected")

    if any_signoff_rejected or (line_statuses and accepted_count == 0):
        final = "rejected"
    elif rejected_count > 0 and accepted_count > 0:
        final = "partial"
    elif all_signoffs_approved and accepted_count > 0 and rejected_count == 0:
        final = "accepted"
    elif accepted_count > 0:
        final = "partial"  # missing some sign-offs but at least one line accepted
    else:
        raise HTTPException(400, "Belum ada keputusan: tidak ada line accepted/rejected dan tidak ada sign-off rejected.")

    with engine.begin() as c:
        c.execute(
            remote_receiving_inspections.update()
            .where(remote_receiving_inspections.c.id == inspection_id)
            .values(status=final, completed_at=datetime.now())
        )
        # If linked to a PO, mark PO received/partial.
        if insp.get("po_id"):
            po_status = "received" if final == "accepted" else ("partial" if final == "partial" else "received")
            c.execute(
                remote_purchase_orders.update()
                .where(remote_purchase_orders.c.id == insp["po_id"])
                .values(status=po_status, received_at=datetime.now())
            )

    db_audit_log(
        action="inspection.finalize",
        user_id=user.get("id"),
        kitchen_id=kitchen["id"],
        org_id=user.get("org_id"),
        target_type="inspection",
        target_id=str(inspection_id),
        before_value={"status": insp.get("status")},
        after_value={"status": final, "lines_accepted": accepted_count, "lines_rejected": rejected_count},
    )
    return db_get_inspection(inspection_id, kitchen["id"])
