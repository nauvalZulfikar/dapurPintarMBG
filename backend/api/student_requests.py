"""Student menu requests (Phase 2A).

Anak-anak / guru sekolah submit "Bu, kelas saya pengen ayam goreng + nasi +
bayam + pisang." Ahli Gizi review, modify, reject, atau confirm. Confirmed
requests bisa di-link sebagai input ke Build Menu Manual flow.

Permissions:
  student_request.view     — list / get          (head_sppg, nutritionist, accountant, aslap)
  student_request.create   — capture new request (nutritionist, aslap)
  student_request.resolve  — confirm / reject    (head_sppg, nutritionist)
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from backend.core.database import (
    engine,
    remote_student_requests,
    db_audit_log,
)
from backend.utils.auth import get_current_user
from backend.utils.permissions import require_permission

router = APIRouter()


VALID_STATUSES = ("open", "confirmed", "rejected", "fulfilled")


class StudentRequestIn(BaseModel):
    request_text:  str = Field(..., min_length=1)
    school_id:     Optional[int] = None
    kelas:         Optional[str] = Field(None, max_length=40)
    student_name:  Optional[str] = Field(None, max_length=100)


class StudentRequestResolve(BaseModel):
    status:           str = Field(..., max_length=20)   # confirmed | rejected | fulfilled
    ahli_gizi_notes:  Optional[str] = None


def _row_to_dict(r) -> dict:
    return {
        "id":              r.id,
        "kitchen_id":      r.kitchen_id,
        "school_id":       r.school_id,
        "kelas":           r.kelas,
        "student_name":    r.student_name,
        "request_text":    r.request_text,
        "status":          r.status,
        "ahli_gizi_notes": r.ahli_gizi_notes,
        "created_by":      r.created_by,
        "created_at":      r.created_at.isoformat() if r.created_at else None,
        "resolved_by":     r.resolved_by,
        "resolved_at":     r.resolved_at.isoformat() if r.resolved_at else None,
    }


@router.get("/student-requests")
async def list_student_requests(
    status: Optional[str] = None,
    kitchen: dict = Depends(require_permission("student_request.view")),
):
    with engine.connect() as c:
        q = select(remote_student_requests).where(
            remote_student_requests.c.kitchen_id == kitchen["id"]
        )
        if status:
            q = q.where(remote_student_requests.c.status == status)
        rows = c.execute(q.order_by(remote_student_requests.c.created_at.desc())).all()
    return {"requests": [_row_to_dict(r) for r in rows]}


@router.post("/student-requests", status_code=201)
async def create_student_request(
    body: StudentRequestIn,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("student_request.create")),
):
    with engine.begin() as c:
        res = c.execute(
            remote_student_requests.insert()
            .values(
                kitchen_id=kitchen["id"],
                school_id=body.school_id,
                kelas=body.kelas,
                student_name=body.student_name,
                request_text=body.request_text,
                status="open",
                created_by=user.get("id"),
            )
            .returning(remote_student_requests.c.id)
        )
        new_id = res.scalar()

    with engine.connect() as c:
        row = c.execute(
            select(remote_student_requests).where(remote_student_requests.c.id == new_id)
        ).first()

    payload = _row_to_dict(row)
    db_audit_log(
        action="student_request.create",
        user_id=user.get("id"),
        kitchen_id=kitchen["id"],
        org_id=user.get("org_id"),
        target_type="student_request",
        target_id=str(new_id),
        after_value=payload,
    )
    return payload


@router.patch("/student-requests/{req_id}")
async def resolve_student_request(
    req_id: int,
    body: StudentRequestResolve,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("student_request.resolve")),
):
    if body.status not in VALID_STATUSES:
        raise HTTPException(400, f"Invalid status. Valid: {', '.join(VALID_STATUSES)}")

    with engine.connect() as c:
        before = c.execute(
            select(remote_student_requests).where(
                (remote_student_requests.c.id == req_id) &
                (remote_student_requests.c.kitchen_id == kitchen["id"])
            )
        ).first()
    if not before:
        raise HTTPException(404, "Request tidak ditemukan.")

    with engine.begin() as c:
        c.execute(
            remote_student_requests.update()
            .where(remote_student_requests.c.id == req_id)
            .values(
                status=body.status,
                ahli_gizi_notes=body.ahli_gizi_notes,
                resolved_by=user.get("id"),
                resolved_at=datetime.now(),
            )
        )

    with engine.connect() as c:
        after = c.execute(
            select(remote_student_requests).where(remote_student_requests.c.id == req_id)
        ).first()

    payload = _row_to_dict(after)
    db_audit_log(
        action=f"student_request.{body.status}",
        user_id=user.get("id"),
        kitchen_id=kitchen["id"],
        org_id=user.get("org_id"),
        target_type="student_request",
        target_id=str(req_id),
        before_value=_row_to_dict(before),
        after_value=payload,
    )
    return payload
