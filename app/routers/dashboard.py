# -*- coding: utf-8 -*-
"""仪表盘接口：只读聚合，供前端大屏使用。"""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import get_db
from app.models import DashboardDay, DashboardSummary
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["仪表盘"])


@router.get(
    "/summary",
    response_model=DashboardSummary,
    summary="仪表盘汇总：KPI / 指标卡 / 指标条",
    responses={404: {"description": "项目不存在"}},
)
def summary(
    project_id: int | None = Query(None, ge=1, description="项目 ID，缺省取第一个项目"),
    con=Depends(get_db),
):
    try:
        return dashboard_service.summary(con, project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/day",
    response_model=DashboardDay,
    summary="某一天的 24 点时序",
    responses={404: {"description": "该日期没有数据"}},
)
def day(
    date: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="日期，缺省取 default_day"),
    con=Depends(get_db),
):
    try:
        return dashboard_service.day(con, date)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
