# backend/api/health.py
import os
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

router = APIRouter()

CLOUD_PRINT_KEY = os.getenv("CLOUD_PRINT_KEY", "")

def check_print_key(x_print_key: Optional[str]):
    if CLOUD_PRINT_KEY and x_print_key != CLOUD_PRINT_KEY:
        raise HTTPException(status_code=403, detail="Invalid print key")

@router.get("/")
def root():
    return {"status": "ok"}

@router.get("/kaithhealth")
async def health_main():
    return {"status": "ok"}

@router.get("/kaithhealthcheck")
@router.get("/kaithheathcheck")  # keep typo route
@router.get("/health")
@router.get("/healthz")
async def health_variants():
    return {"status": "ok"}
