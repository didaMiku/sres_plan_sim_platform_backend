# -*- coding: utf-8 -*-
"""导入业务：读文件 → 按映射改名 → 清洗 → UPSERT 入库。"""

import io
import math
import os
import re
import uuid
from datetime import datetime

import pandas as pd

from app import db

# 目前只做这三类；tariff 是"时段→价格"，要单独展开成 24 行，以后再说
TABLES = {
    "source": "t_source",
    "typical_day": "t_typical_day",
    "simulation": "t_simulation",
}


def import_bytes(con, admin_id: int, type_code: str, filename: str, content: bytes, mapping: dict) -> dict:
    if type_code not in TABLES:
        raise ValueError("该类型暂未支持")
    filename = _clean_name(filename)  # 兼容个别客户端把中文文件名做 RFC2047 编码
    table = TABLES[type_code]

    # 字段字典：判断哪些是合法字段、哪些必填
    fields = db.list_fields_by_type(con, type_code)
    field_keys = {f["field_key"] for f in fields}
    required = [f["field_key"] for f in fields if f["required"]]

    # 校验前端传的映射
    bad = sorted({v for v in mapping.values() if v and v not in field_keys})
    if bad:
        raise ValueError(f"映射到不存在的字段：{'、'.join(bad)}")
    mapped = {v for v in mapping.values() if v}
    missing = [k for k in required if k not in mapped]
    if missing:
        raise ValueError(f"缺少必填列：{'、'.join(missing)}")

    df = _read(filename, content)
    df = df.rename(columns={src: dst for src, dst in mapping.items() if dst})

    if "ts" not in df.columns:
        raise ValueError("缺少时间戳列")

    # 时间戳统一成 2026-01-01 00:00:00
    df["ts"] = pd.to_datetime(df["ts"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")

    # 数值列转数字，转不了的变 NaN
    value_cols = [k for k in field_keys if k != "ts" and k in df.columns]
    for col in value_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # 空字符串也算空；必填字段为空的行丢掉
    df = df.replace(r"^\s*$", pd.NA, regex=True)
    before = len(df)
    df = df.dropna(subset=[c for c in required if c in df.columns])
    df = df[df["ts"].notna()]
    dropped = before - len(df)

    # 同一时刻保留最后一条，按时间排序
    df = df.drop_duplicates(subset=["ts"], keep="last").sort_values("ts")

    cols = ["ts"] + value_cols
    rows = _rows(df, cols)
    stored = _save_raw(filename, content)

    # 目标表 + 导入记录放在一个事务里，出错一起回滚
    sql = (
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(['?'] * len(cols))}) "
        f"ON CONFLICT(ts) DO UPDATE SET " + ", ".join(f"{c}=excluded.{c}" for c in value_cols)
    )
    with con:
        con.executemany(sql, rows)
        con.execute(
            "INSERT INTO import_record (admin_id, type_code, original_filename, stored_filename, "
            "row_count, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (admin_id, type_code, filename, stored, len(df), "success", db.now_text()),
        )

    return {"row_count": len(df), "dropped": dropped, "table": table}


def _read(filename: str, content: bytes) -> pd.DataFrame:
    if filename.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(content))
    try:
        return pd.read_csv(io.BytesIO(content), encoding="utf-8-sig")
    except UnicodeDecodeError:
        return pd.read_csv(io.BytesIO(content), encoding="gbk")


def _rows(df, cols):
    for rec in df[cols].itertuples(index=False, name=None):
        yield tuple(None if (isinstance(v, float) and math.isnan(v)) else v for v in rec)


def _clean_name(name: str) -> str:
    # 个别客户端（如 PowerShell 的 -Form）会把中文文件名做 RFC2047 编码，先解码
    try:
        from email.header import decode_header

        parts = decode_header(name)
        name = "".join(p.decode(enc or "utf-8") if isinstance(p, bytes) else p for p, enc in parts)
    except Exception:
        pass
    # 去掉 Windows 文件名里的非法字符
    name = re.sub(r'[\\/:*?"<>|]', "_", name).strip()
    return name or "upload"


def _save_raw(filename: str, content: bytes) -> str:
    db.RAW_DIR.mkdir(parents=True, exist_ok=True)
    safe = _clean_name(os.path.basename(filename))
    stored = f"{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}__{safe}"
    (db.RAW_DIR / stored).write_bytes(content)
    return stored
