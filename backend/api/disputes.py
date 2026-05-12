"""Supplier disputes (Phase 3).

Auto-created when Ahli Gizi rejects a bahan in Joint Inspection.
Read by head_sppg, accountant, nutritionist; resolved by accountant + head_sppg
(usually after supplier responds).
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.core.database import (
    engine,
    remote_supplier_disputes,
    db_list_supplier_disputes,
    db_audit_log,
)
from backend.utils.auth import get_current_user
from backend.utils.permissions import require_permission

router = APIRouter()


class DisputeResolve(BaseModel):
    status:           str = Field(..., max_length=20)   # resolved | closed
    resolution_notes: Optional[str] = None


@router.get("/disputes")
async def list_disputes(
    status: Optional[str] = None,
    kitchen: dict = Depends(require_permission("dispute.view")),
):
    return {"disputes": db_list_supplier_disputes(kitchen["id"], status=status)}


@router.patch("/disputes/{dispute_id}")
async def resolve_dispute(
    dispute_id: int,
    body: DisputeResolve,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("dispute.resolve")),
):
    if body.status not in ("resolved", "closed"):
        raise HTTPException(400, "Status harus 'resolved' atau 'closed'.")

    from sqlalchemy import select
    with engine.connect() as c:
        before = c.execute(
            select(remote_supplier_disputes).where(
                (remote_supplier_disputes.c.id == dispute_id) &
                (remote_supplier_disputes.c.kitchen_id == kitchen["id"])
            )
        ).first()
    if not before:
        raise HTTPException(404, "Dispute tidak ditemukan.")

    with engine.begin() as c:
        c.execute(
            remote_supplier_disputes.update()
            .where(remote_supplier_disputes.c.id == dispute_id)
            .values(
                status=body.status,
                resolution_notes=body.resolution_notes,
                resolved_at=datetime.now(),
            )
        )

    db_audit_log(
        action=f"dispute.{body.status}",
        user_id=user.get("id"),
        kitchen_id=kitchen["id"],
        org_id=user.get("org_id"),
        target_type="dispute",
        target_id=str(dispute_id),
        before_value={"status": before.status},
        after_value={"status": body.status, "resolution_notes": body.resolution_notes},
    )

    rows = db_list_supplier_disputes(kitchen["id"])
    return next((d for d in rows if d["id"] == dispute_id), {"id": dispute_id})
