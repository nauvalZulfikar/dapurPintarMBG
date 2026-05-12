"""Supplier master CRUD (Phase 1).

Permissions:
  supplier.view    — list / get          (head_sppg, accountant, nutritionist, aslap)
  supplier.manage  — create / update / delete  (head_sppg, accountant)
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.core.database import (
    engine,
    remote_suppliers,
    db_list_suppliers,
    db_get_supplier,
    db_audit_log,
)
from backend.utils.auth import get_current_user
from backend.utils.permissions import require_permission

router = APIRouter()


class SupplierIn(BaseModel):
    name:      str = Field(..., min_length=1, max_length=150)
    contact:   Optional[str] = Field(None, max_length=100)
    npwp:      Optional[str] = Field(None, max_length=30)
    rekening:  Optional[str] = Field(None, max_length=50)
    bank_name: Optional[str] = Field(None, max_length=50)
    kategori:  Optional[str] = Field(None, max_length=50)
    rating:    int = Field(5, ge=1, le=5)
    notes:     Optional[str] = None


class SupplierPatch(BaseModel):
    name:      Optional[str] = Field(None, min_length=1, max_length=150)
    contact:   Optional[str] = Field(None, max_length=100)
    npwp:      Optional[str] = Field(None, max_length=30)
    rekening:  Optional[str] = Field(None, max_length=50)
    bank_name: Optional[str] = Field(None, max_length=50)
    kategori:  Optional[str] = Field(None, max_length=50)
    rating:    Optional[int] = Field(None, ge=1, le=5)
    notes:     Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/suppliers")
async def list_suppliers(
    include_inactive: bool = False,
    kitchen: dict = Depends(require_permission("supplier.view")),
):
    return {"suppliers": db_list_suppliers(kitchen["id"], active_only=not include_inactive)}


@router.get("/suppliers/{supplier_id}")
async def get_supplier(
    supplier_id: int,
    kitchen: dict = Depends(require_permission("supplier.view")),
):
    s = db_get_supplier(supplier_id, kitchen["id"])
    if s is None:
        raise HTTPException(404, "Supplier not found")
    return s


@router.post("/suppliers", status_code=201)
async def create_supplier(
    body: SupplierIn,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("supplier.manage")),
):
    with engine.begin() as c:
        res = c.execute(
            remote_suppliers.insert()
            .values(kitchen_id=kitchen["id"], **body.model_dump(), is_active=True)
            .returning(remote_suppliers.c.id)
        )
        new_id = res.scalar()

    supplier = db_get_supplier(new_id, kitchen["id"])
    db_audit_log(
        action="supplier.create",
        user_id=user.get("id"),
        kitchen_id=kitchen["id"],
        org_id=user.get("org_id"),
        target_type="supplier",
        target_id=str(new_id),
        after_value=supplier,
    )
    return supplier


@router.patch("/suppliers/{supplier_id}")
async def patch_supplier(
    supplier_id: int,
    body: SupplierPatch,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("supplier.manage")),
):
    before = db_get_supplier(supplier_id, kitchen["id"])
    if before is None:
        raise HTTPException(404, "Supplier not found")

    values = {k: v for k, v in body.model_dump().items() if v is not None}
    if not values:
        raise HTTPException(400, "No fields to update")

    with engine.begin() as c:
        res = c.execute(
            remote_suppliers.update()
            .where(
                (remote_suppliers.c.id == supplier_id) &
                (remote_suppliers.c.kitchen_id == kitchen["id"])
            )
            .values(**values)
        )
        if res.rowcount == 0:
            raise HTTPException(404, "Supplier not found")

    after = db_get_supplier(supplier_id, kitchen["id"])
    db_audit_log(
        action="supplier.update",
        user_id=user.get("id"),
        kitchen_id=kitchen["id"],
        org_id=user.get("org_id"),
        target_type="supplier",
        target_id=str(supplier_id),
        before_value=before,
        after_value=after,
    )
    return after


@router.delete("/suppliers/{supplier_id}")
async def delete_supplier(
    supplier_id: int,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("supplier.manage")),
):
    """Soft-delete: flips `is_active=false`. Hard delete reserved for ops."""
    before = db_get_supplier(supplier_id, kitchen["id"])
    if before is None:
        raise HTTPException(404, "Supplier not found")

    with engine.begin() as c:
        c.execute(
            remote_suppliers.update()
            .where(
                (remote_suppliers.c.id == supplier_id) &
                (remote_suppliers.c.kitchen_id == kitchen["id"])
            )
            .values(is_active=False)
        )

    after = db_get_supplier(supplier_id, kitchen["id"])
    db_audit_log(
        action="supplier.deactivate",
        user_id=user.get("id"),
        kitchen_id=kitchen["id"],
        org_id=user.get("org_id"),
        target_type="supplier",
        target_id=str(supplier_id),
        before_value=before,
        after_value=after,
    )
    return {"ok": True}
