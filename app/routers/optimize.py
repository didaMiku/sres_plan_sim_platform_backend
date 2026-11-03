# -*- coding: utf-8 -*-
"""容量优化接口"""

from fastapi import APIRouter, Depends

from app.db import get_db
from app.services import optimize_service

router = APIRouter(prefix="/optimize", tags=["优化"])


@router.post("", summary="PSO 容量优化：总成本最小")
def run(con=Depends(get_db)):
    return optimize_service.optimize(con)
