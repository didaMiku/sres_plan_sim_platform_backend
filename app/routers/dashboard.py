# -*- coding: utf-8 -*-
"""仪表盘接口：只读聚合，供前端大屏使用。"""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import get_db
from app.models import DashboardDay, DashboardDay15, DashboardForecast, DashboardSummary
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


@router.get(
    "/day-15",
    response_model=DashboardDay15,
    summary="某一天的 15 分钟时序",
)
def day_15(
    date: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="日期，缺省取 15 分钟数据的第一天"),
    con=Depends(get_db),
):
    return dashboard_service.day_15(con, date)


@router.get(
    "/forecast",
    response_model=DashboardForecast,
    summary="负荷、风电或光伏预测",
)
def forecast(
    target: str = Query("load", pattern="^(load|wind|pv)$", description="预测目标：load 负荷、wind 风电、pv 光伏"),
    date: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="日期，缺省取数据最后一天"),
    con=Depends(get_db),
):
    try:
        return dashboard_service.forecast(con, date, target)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
