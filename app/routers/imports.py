# -*- coding: utf-8 -*-
"""数据导入接口：接文件 + 映射，清洗后入库。"""

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from app.db import get_db, list_import_records
from app.models import ImportRecordItem, ImportResult
from app.security import current_admin
from app.services import imports_service

router = APIRouter(prefix="/imports", tags=["数据导入"])


# 导入历史：当前管理员最近的导入记录
@router.get("", response_model=list[ImportRecordItem], summary="导入历史")
def history(
    con=Depends(get_db),
    admin=Depends(current_admin),
    limit: int = Query(20, ge=1, le=100),
):
    rows = list_import_records(con, admin["admin_id"], limit)
    return [
        {
            "id": r["id"],
            "type_code": r["type_code"],
            "original_filename": r["original_filename"],
            "row_count": r["row_count"],
            "status": r["status"],
            "error_message": r["error_message"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


# 上传并导入：前端一次提交 文件 + 类型 + 列映射
@router.post("", response_model=ImportResult, summary="导入数据文件")
async def upload(
    file: UploadFile = File(..., description="csv 或 xlsx"),
    type_code: str = Form(..., description="source / typical_day / simulation"),
    mapping: str = Form(..., description='JSON：{"原始列名": "数据库字段"}'),
    con=Depends(get_db),
    admin=Depends(current_admin),
):
    content = await file.read()

    try:
        payload = json.loads(mapping)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="mapping 不是合法的 JSON")

    try:
        return imports_service.import_bytes(
            con,
            admin["admin_id"],
            type_code,
            file.filename or "upload",
            content,
            payload,
        )
    except ValueError as e:  # 业务校验失败（缺列、类型不支持等）
        raise HTTPException(status_code=400, detail=str(e))
