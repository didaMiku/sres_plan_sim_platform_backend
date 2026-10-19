# -*- coding: utf-8 -*-
"""≈ @RestController：登录接口
"""

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status

from app.db import get_db # 依赖：每个请求一个数据库连接
from app.models import AdminInfo, LoginRequest, LoginResponse # 登录相关的请求/响应模型
from app.security import COOKIE_NAME, current_admin # Cookie 名 + 登录态校验
from app.services import auth_service # 业务层

router = APIRouter(prefix="/auth", tags=["登录"])       # 路由组；完整路径 = /api + /auth + /xxx


# 登入接口：POST /api/auth/login
@router.post(
    "/login",
    response_model=LoginResponse, 
    summary="管理员登录",
    responses={401: {"description": "用户名或密码错误 / 账号已停用"}},
)
def login(
    body: LoginRequest,
    response: Response,
    conn=Depends(get_db),  # 注入数据库连接
):
    data, err = auth_service.login(conn, body.username, body.password)
    if err or data is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=err or "登录失败")
    response.set_cookie(
        COOKIE_NAME,
        data["token"],
        httponly=True,
        samesite="lax",
        max_age=data["expires_in"],
    )
    return data # 返回 JSON，含 token


# 当前登录状态：GET /api/auth/me，不带 Cookie 或 token 过期返回 401
@router.get(
        "/me", 
        response_model=AdminInfo, 
        summary="当前登录的管理员"
)
def me(session=Depends(current_admin)):
    return {
        "id": session["admin_id"],
        "username": session["username"],
        "display_name": session["display_name"],
        "role": session["role"],
    }


# 退出登录：POST /api/auth/logout，删会话 + 清 Cookie，重复调用也安全
@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="退出登录")
def logout(
    token: str | None = Cookie(default=None, alias=COOKIE_NAME),
    conn=Depends(get_db),
):
    auth_service.logout(conn, token)
    resp = Response(status_code=status.HTTP_204_NO_CONTENT)
    resp.delete_cookie(COOKIE_NAME)  # 让浏览器把 Cookie 删掉
    return resp
