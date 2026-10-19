# -*- coding: utf-8 -*-
"""≈ DataSource + Repository：数据访问层（SQLite）
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "app.db"        # 数据库文件
RAW_DIR = BASE_DIR / "data" / "raw"           # 上传原件目录
SCHEMA_PATH = BASE_DIR / "sql" / "schema.sql" # 建表脚本


# ==================== 基础工具 ====================
def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S") # 统一时间格式：YYYY-MM-DD HH:MM:SS


# 开一个连接
def connect():                                         
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON") # SQLite 默认不检查外键，必须显式打开
    return con


# 依赖注入用：每个请求一个连接
def get_db():
    con = connect() # 打开
    try:
        yield con # 交给接口/业务层用
    finally:
        con.close() # 请求结束自动关闭


# 建表 + 插入默认管理员，不覆盖
def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = connect()
    con.executescript(SCHEMA_PATH.read_text(encoding="utf-8")) # 执行 schema.sql
    exists = con.execute("SELECT 1 FROM admin WHERE username = ?", ("admin",)).fetchone() # 是否已有默认的 admin
    if not exists: # 没有就插入默认账号
        con.execute(
            "INSERT INTO admin (username, display_name, password, role, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("admin", "zpr", "1234", "admin", 1, now_text()),
        )
        con.commit()
    con.close()


# ==================== admin 表 ====================

# 按登录名查管理员
def admin_find_by_username(con, username: str):
    return con.execute(
        "SELECT * FROM admin WHERE username = ?",
        (username,),
    ).fetchone()


# 按 id 查管理员
def admin_find_by_id(con, admin_id: int):
    return con.execute("SELECT * FROM admin WHERE id = ?", (admin_id,)).fetchone()



# ==================== admin_session 表 ====================

# 新建一次登录会话
def session_create(con, token: str, admin_id: int, hours: int = 8):
    created = now_text()
    expires = (datetime.now() + timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    con.execute(
        "INSERT INTO admin_session (token, admin_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (token, admin_id, created, expires),
    )
    con.commit()


# 按 token 查会话，顺带带出管理员信息
def session_find(con, token: str):
    row = con.execute(
        "SELECT s.id AS session_id, s.admin_id, s.expires_at, "
        "       a.username, a.display_name, a.role "
        "FROM admin_session s JOIN admin a ON a.id = s.admin_id "
        "WHERE s.token = ?",
        (token,),
    ).fetchone()
    if row is None: # token 不存在
        return None
    if row["expires_at"] < now_text(): # 已过期，格式固定，字符串比较即时间比较
        con.execute("DELETE FROM admin_session WHERE id = ?", (row["session_id"],)) # 顺手删掉
        con.commit()
        return None
    return row


# 退出登录：删掉这一行
def session_delete(con, token: str):
    con.execute("DELETE FROM admin_session WHERE token = ?", (token,))
    con.commit()


# 清理所有过期会话，登录时顺手的事儿
def session_purge_expired(con):
    con.execute("DELETE FROM admin_session WHERE expires_at < ?", (now_text(),))
    con.commit()
