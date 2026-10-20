# -*- coding: utf-8 -*-
"""数据字典接口：给前端选类型、开关联字段用。"""

from fastapi import APIRouter, Depends

from app import db
from app.db import get_db
from app.models import DataTypeItem

router = APIRouter(prefix="/schema", tags=["数据字典"])


# 4 类数据类型 + 每类包含的字段
@router.get("/types", response_model=list[DataTypeItem], summary="数据类型与字段")
def types(con=Depends(get_db)):
    result = []
    for t in db.list_data_types(con):
        rows = db.list_fields_by_type(con, t["code"])
        result.append({
            "code": t["code"],
            "name": t["name"],
            "description": t["description"],
            "fields": [
                {
                    "key": f["field_key"],
                    "name": f["field_name"] or f["field_key"],  # 中文名允许为空，空了就用列名兜底
                    "unit": f["unit"] or "",
                    "required": bool(f["required"]),
                    "sort_order": f["sort_order"] or 0,
                }
                for f in rows
            ],
        })
    return result
