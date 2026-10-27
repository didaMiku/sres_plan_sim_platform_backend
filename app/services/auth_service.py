# -*- coding: utf-8 -*-
"""≈ @Service：登录接口业务实现
"""

import secrets # 生成随机 token

from app import db

SESSION_HOURS = 8 # 会话有效期（小时）


# 登入服务：返回 (结果字典, 错误信息)；成功时错误信息为 None
def login(conn, username: str, password: str):         
    admin = db.admin_find_by_username(conn, username)
    if admin is None:
        return None, "用户名或密码错误" 
    if admin["status"] != 1:
        return None, "账号已停用"
    if admin["password"] != password:
        return None, "用户名或密码错误"

    # 登录时顺手清理过期会话
    db.session_purge_expired(conn)
    token = secrets.token_urlsafe(32)    
    db.session_create(conn, token, admin["id"], SESSION_HOURS)

    return {
        "token": token,
        "expires_in": SESSION_HOURS * 3600,
        "admin": {
            "id": admin["id"],
            "username": admin["username"],
            "display_name": admin["display_name"],
            "role": admin["role"],
        },
    }, None


# 登出服务：删掉会话记录（token 为空也安全）
def logout(conn, token: str | None):
    if token:
        db.session_delete(conn, token)
