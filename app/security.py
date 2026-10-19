# -*- coding: utf-8 -*-
"""
登录态校验：从 Cookie 取 token，查 admin_session
"""

from fastapi import Cookie, Depends, HTTPException

from app import db
from app.db import get_db

COOKIE_NAME = "admin_token"


# 当前登录的管理员；需要登录的接口写 Depends(current_admin) 即可
def current_admin(conn=Depends(get_db), token: str | None = Cookie(default=None, alias=COOKIE_NAME)):
    if not token:  # 没带 Cookie
        raise HTTPException(status_code=401, detail="未登录")
    session = db.session_find(conn, token)
    if session is None:  # token 不存在或已过期
        raise HTTPException(status_code=401, detail="登录已过期")
    return session
