# -*- coding: utf-8 -*-
"""≈ DTO / VO：登录接口的请求与响应模型
"""

from pydantic import BaseModel, Field # BaseModel = 模型基类；Field 加约束与说明


# 登录请求体
class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64, description="管理员用户名") # 必填
    password: str = Field(..., min_length=1, max_length=128, description="密码") # 必填


# 返回给前端的管理员信息（不含密码）
class AdminInfo(BaseModel):
    id: int           # 主键
    username: str     # 登录名
    display_name: str # 显示名（界面右上角那个）
    role: str         # 角色


# 登录成功的响应体
class LoginResponse(BaseModel):
    token: str       # 会话令牌（同时写进 Set-Cookie）
    expires_in: int  # 有效期秒数（8 小时 = 28800）
    admin: AdminInfo # 管理员信息
