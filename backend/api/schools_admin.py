"""School master CRUD (Phase 1).

Replaces the read-only `/api/schools` JSON-file endpoint with kitchen-scoped
DB-backed CRUD. The legacy GET endpoint in `data.py` remains as a transparent
proxy to `db_list_schools()` so existing frontend callers keep working.

Permissions:
  school.view    — list / get          (head_sppg, nutritionist, accountant, aslap, head_kitchen)
  school.manage  — create / update / delete  (head_sppg only)
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from backend.core.database import (
    engine,
    remote_schools,
    db_list_schools,
    db_get_school,
    db_audit_log,
)
from backend.utils.auth import get_current_user
from backend.utils.permissions import require_permission

router = APIRouter()


VALID_LEVELS = ("PAUD", "TK", "SD", "SMP", "SMA")


class SchoolIn(BaseModel):
    name:          str = Field(..., min_length=1, max_length=150)
    address:       Optional[str] = None
    level:         str = Field(..., max_length=20)
    age_group:     str = Field(..., max_length=50)
    student_count: int = Field(0, ge=0)
    distance:      int = Field(0, ge=0)
    gps_lat:       Optional[str] = None
    gps_long:      Optional[str] = None
    contact:       Optional[str] = Field(None, max_length=100)


class SchoolPatch(BaseModel):
    name:          Optional[str] = Field(None, min_length=1, max_length=150)
    address:       Optional[str] = None
    level:         Optional[str] = Field(None, max_length=20)
    age_group:     Optional[str] = Field(None, max_length=50)
    student_count: Optional[int] = Field(None, ge=0)
    distance:      Optional[int] = Field(None, ge=0)
    gps_lat:       Optional[str] = None
    gps_long:      Optional[str] = None
    contact:       Optional[str] = Field(None, max_length=100)
    is_active:     Optional[bool] = None


def _validate_level(level: str) -> None:
    if level not in VALID_LEVELS:
        raise HTTPException(400, f"Invalid level. Valid: {', '.join(VALID_LEVELS)}")


@router.get("/admin/schools")
async def list_schools_admin(
    include_inactive: bool = False,
    kitchen: dict = Depends(require_permission("school.view")),
):
    """Admin list — same data as `/api/schools` but with `is_active=false` rows."""
    return {"schools": db_list_schools(kitchen["id"], active_only=not include_inactive)}


@router.post("/admin/schools", status_code=201)
async def create_school(
    body: SchoolIn,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("school.manage")),
):
    _validate_level(body.level)
    with engine.begin() as c:
        res = c.execute(
            remote_schools.insert()
            .values(
                kitchen_id=kitchen["id"],
                name=body.name,
                address=body.address,
                level=body.level,
                age_group=body.age_group,
                student_count=body.student_count,
                distance=body.distance,
                gps_lat=body.gps_lat,
                gps_long=body.gps_long,
                contact=body.contact,
                is_active=True,
            )
            .returning(remote_schools.c.id)
        )
        new_id = res.scalar()

    school = db_get_school(new_id, kitchen["id"])
    db_audit_log(
        action="school.create",
        user_id=user.get("id"),
        kitchen_id=kitchen["id"],
        org_id=user.get("org_id"),
        target_type="school",
        target_id=str(new_id),
        after_value=school,
    )
    return school


@router.patch("/admin/schools/{school_id}")
async def patch_school(
    school_id: int,
    body: SchoolPatch,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("school.manage")),
):
    before = db_get_school(school_id, kitchen["id"])
    if before is None:
        raise HTTPException(404, "School not found")
    if body.level is not None:
        _validate_level(body.level)

    values = {k: v for k, v in body.model_dump().items() if v is not None}
    if not values:
        raise HTTPException(400, "No fields to update")

    with engine.begin() as c:
        res = c.execute(
            remote_schools.update()
            .where(
                (remote_schools.c.id == school_id) &
                (remote_schools.c.kitchen_id == kitchen["id"])
            )
            .values(**values)
        )
        if res.rowcount == 0:
            raise HTTPException(404, "School not found")

    after = db_get_school(school_id, kitchen["id"])
    db_audit_log(
        action="school.update",
        user_id=user.get("id"),
        kitchen_id=kitchen["id"],
        org_id=user.get("org_id"),
        target_type="school",
        target_id=str(school_id),
        before_value=before,
        after_value=after,
    )
    return after


@router.delete("/admin/schools/{school_id}")
async def delete_school(
    school_id: int,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("school.manage")),
):
    """Soft-delete: flips `is_active=false`. Hard delete reserved for ops."""
    before = db_get_school(school_id, kitchen["id"])
    if before is None:
        raise HTTPException(404, "School not found")

    with engine.begin() as c:
        c.execute(
            remote_schools.update()
            .where(
                (remote_schools.c.id == school_id) &
                (remote_schools.c.kitchen_id == kitchen["id"])
            )
            .values(is_active=False)
        )

    after = db_get_school(school_id, kitchen["id"])
    db_audit_log(
        action="school.deactivate",
        user_id=user.get("id"),
        kitchen_id=kitchen["id"],
        org_id=user.get("org_id"),
        target_type="school",
        target_id=str(school_id),
        before_value=before,
        after_value=after,
    )
    return {"ok": True}
