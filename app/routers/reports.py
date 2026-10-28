# -*- coding: utf-8 -*-
"""报告生成接口：一次生成 Markdown 直接返回，不存库。"""

from fastapi import APIRouter, Depends, HTTPException

from app.db import get_db
from app.models import ReportRequest, ReportResponse
from app.services import report_service

router = APIRouter(prefix="/reports", tags=["报告"])


@router.post(
    "",
    response_model=ReportResponse,
    summary="按选中章节生成 Markdown 报告",
    responses={400: {"description": "未选择章节"}},
)
def create(
    body: ReportRequest,
    con=Depends(get_db),
):
    try:
        return report_service.build_report(con, body.title, body.sections)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
