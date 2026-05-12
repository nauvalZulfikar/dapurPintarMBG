"""Purchase Orders (Phase 3).

Akuntan generates PO from Phase 2B forecast (or manually). PO drives the
Joint Inspection PO checklist when bahan datang at receiving.

Permissions:
  po.view    — head_sppg, accountant, nutritionist, aslap
  po.create  — head_sppg, accountant
  po.edit    — head_sppg, accountant
  po.delete  — head_sppg, accountant (only while status='draft')
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from backend.core.database import (
    engine,
    remote_purchase_orders,
    remote_po_lines,
    db_list_purchase_orders, db_get_purchase_order,
    db_audit_log,
)
from backend.utils.auth import get_current_user
from backend.utils.permissions import require_permission

router = APIRouter()

VALID_PO_STATUSES = ("draft", "sent", "partial", "received", "closed", "cancelled")


class POLineIn(BaseModel):
    item_name:           str = Field(..., min_length=1, max_length=150)
    item_code:           Optional[str] = Field(None, max_length=50)
    total_weight_grams:  int = Field(..., ge=0)
    unit:                str = Field("kg", max_length=20)
    expected_containers: int = Field(1, ge=1)
    unit_price_idr:      int = Field(0, ge=0)
    notes:               Optional[str] = None


class POIn(BaseModel):
    supplier_id:            int
    expected_delivery_date: Optional[str] = None
    notes:                  Optional[str] = None
    lines:                  List[POLineIn] = Field(default_factory=list)


class POPatch(BaseModel):
    status:                 Optional[str] = None
    expected_delivery_date: Optional[str] = None
    notes:                  Optional[str] = None


@router.get("/purchase-orders")
async def list_purchase_orders(
    status: Optional[str] = None,
    supplier_id: Optional[int] = None,
    kitchen: dict = Depends(require_permission("po.view")),
):
    return {"purchase_orders": db_list_purchase_orders(kitchen["id"], status=status, supplier_id=supplier_id)}


@router.get("/purchase-orders/{po_id}")
async def get_po(po_id: int, kitchen: dict = Depends(require_permission("po.view"))):
    po = db_get_purchase_order(po_id, kitchen["id"])
    if not po:
        raise HTTPException(404, "PO tidak ditemukan.")
    return po


@router.post("/purchase-orders", status_code=201)
async def create_po(
    body: POIn,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("po.create")),
):
    line_total_sum = 0
    line_calcs: list[dict] = []
    for ln in body.lines:
        # Normalize unit price to per-kg if user passed it. Total = price × (weight in kg).
        kg = ln.total_weight_grams / 1000.0
        line_total = int(round(ln.unit_price_idr * kg))
        line_calcs.append({**ln.model_dump(), "line_total_idr": line_total})
        line_total_sum += line_total

    with engine.begin() as c:
        res = c.execute(
            remote_purchase_orders.insert()
            .values(
                kitchen_id=kitchen["id"],
                supplier_id=body.supplier_id,
                status="draft",
                expected_delivery_date=body.expected_delivery_date,
                total_amount_idr=line_total_sum,
                notes=body.notes,
                created_by=user.get("id"),
            )
            .returning(remote_purchase_orders.c.id)
        )
        new_po_id = res.scalar()

        for ln in line_calcs:
            c.execute(
                remote_po_lines.insert().values(po_id=new_po_id, **ln)
            )

    po = db_get_purchase_order(new_po_id, kitchen["id"])
    db_audit_log(
        action="po.create",
        user_id=user.get("id"),
        kitchen_id=kitchen["id"],
        org_id=user.get("org_id"),
        target_type="purchase_order",
        target_id=str(new_po_id),
        after_value={"supplier_id": body.supplier_id, "total": line_total_sum, "lines": len(body.lines)},
    )
    return po


@router.patch("/purchase-orders/{po_id}")
async def patch_po(
    po_id: int,
    body: POPatch,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("po.edit")),
):
    before = db_get_purchase_order(po_id, kitchen["id"])
    if not before:
        raise HTTPException(404, "PO tidak ditemukan.")
    if body.status and body.status not in VALID_PO_STATUSES:
        raise HTTPException(400, f"Invalid status. Valid: {', '.join(VALID_PO_STATUSES)}")

    values: dict = {}
    if body.status is not None:
        values["status"] = body.status
        if body.status == "sent" and not before.get("sent_at"):
            values["sent_at"] = datetime.now()
        elif body.status == "received" and not before.get("received_at"):
            values["received_at"] = datetime.now()
    if body.expected_delivery_date is not None:
        values["expected_delivery_date"] = body.expected_delivery_date
    if body.notes is not None:
        values["notes"] = body.notes

    if not values:
        raise HTTPException(400, "No fields to update")

    with engine.begin() as c:
        c.execute(
            remote_purchase_orders.update()
            .where(
                (remote_purchase_orders.c.id == po_id) &
                (remote_purchase_orders.c.kitchen_id == kitchen["id"])
            )
            .values(**values)
        )

    after = db_get_purchase_order(po_id, kitchen["id"])
    db_audit_log(
        action="po.update",
        user_id=user.get("id"),
        kitchen_id=kitchen["id"],
        org_id=user.get("org_id"),
        target_type="purchase_order",
        target_id=str(po_id),
        before_value={"status": before.get("status")},
        after_value={"status": after.get("status")},
    )
    return after


@router.delete("/purchase-orders/{po_id}")
async def delete_po(
    po_id: int,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("po.delete")),
):
    before = db_get_purchase_order(po_id, kitchen["id"])
    if not before:
        raise HTTPException(404, "PO tidak ditemukan.")
    if before.get("status") != "draft":
        raise HTTPException(400, f"Hanya PO status='draft' yang bisa dihapus. Status sekarang: {before.get('status')}")

    with engine.begin() as c:
        c.execute(
            remote_purchase_orders.delete().where(
                (remote_purchase_orders.c.id == po_id) &
                (remote_purchase_orders.c.kitchen_id == kitchen["id"])
            )
        )

    db_audit_log(
        action="po.delete",
        user_id=user.get("id"),
        kitchen_id=kitchen["id"],
        org_id=user.get("org_id"),
        target_type="purchase_order",
        target_id=str(po_id),
        before_value={"supplier_id": before.get("supplier_id"), "total": before.get("total_amount_idr")},
    )
    return {"ok": True}
