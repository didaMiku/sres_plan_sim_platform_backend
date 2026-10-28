# -*- coding: utf-8 -*-
"""≈ Application.java：整个后端的入口

用来创建应用、挂中间件、注册路由、健康检查
"""

from fastapi import FastAPI 
from fastapi.middleware.cors import CORSMiddleware 

from app import db 
from app.routers import auth, dashboard, imports, reports, schema

# 应用实例
app = FastAPI(
    title="友好型源网荷储一体化规划配置仿真平台",
    version="0.1.0",
    description="后端接口（当前：登录模块）",
)

app.add_middleware(                                    
    CORSMiddleware,
    allow_origins=["http://localhost:5173",
                   "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# db.init_db()

app.include_router(auth.router, prefix="/api") # 注册登录路由：/api/auth/
app.include_router(schema.router, prefix="/api") # 注册数据字典路由：/api/schema/types
app.include_router(imports.router, prefix="/api") # 注册导入路由：/api/imports
app.include_router(dashboard.router, prefix="/api") # 注册仪表盘路由：/api/dashboard/summary
app.include_router(reports.router, prefix="/api") # 注册报告路由：/api/reports


# 健康检查接口
@app.get("/health", tags=["运维"])
def health():
    return {"status": "ok", "version": app.version}
