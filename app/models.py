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


# ==================== 数据字典 ====================

# 一个数据库字段
class FieldItem(BaseModel):
    key: str             # 数据库真列名，如 wind_speed
    name: str            # 中文名，如 风速
    unit: str = ''       # 单位，如 m/s
    required: bool = False
    sort_order: int = 0


# 一类数据 + 它包含的字段
class DataTypeItem(BaseModel):
    code: str                        # source / typical_day / simulation / tariff
    name: str                        # 源荷气象数据
    description: str | None = None   # 一行说明
    fields: list[FieldItem] = Field(default_factory=list)


# ==================== 导入 ====================

# 导入成功的返回
class ImportResult(BaseModel):
    row_count: int                   # 实际写入行数
    dropped: int = 0                 # 因为必填为空被丢掉的行数
    table: str                       # 写进了哪张表


# 一条导入历史
class ImportRecordItem(BaseModel):
    id: int
    type_code: str
    original_filename: str
    row_count: int
    status: str
    error_message: str | None = None
    created_at: str


# ==================== 仪表盘 ====================

# 顶部 KPI
class KpiItem(BaseModel):
    key: str                 # 指标键，前端配色/下钻用
    label: str               # 中文名
    en: str = ""             # 英文副标题
    value: float
    unit: str = ""
    caliber: str = ""        # 口径说明，前端 tooltip 展示


# 底部指标卡
class CardItem(BaseModel):
    key: str
    label: str
    value: float | str       # 装机是数字，储能是 "20 MW / 80 MWh"
    unit: str = ""


# 底部指标条
class IndicatorItem(BaseModel):
    key: str
    label: str
    value: float
    unit: str = "%"


# 仪表盘汇总响应
class DashboardSummary(BaseModel):
    project: dict
    kpi: list[KpiItem]
    cards: list[CardItem]
    indicators: list[IndicatorItem]
    meta: dict


# ==================== 仪表盘时序 ====================

# 平衡图：供给各项加负荷
class BalanceSeries(BaseModel):
    wind: list[float]
    pv: list[float]
    discharge: list[float]
    buy: list[float]
    load: list[float]


# 风电或光伏：实际出力加装机上限
class RenewableSeries(BaseModel):
    actual: list[float]
    capacity: float


# 储能：充电、放电、SOC
class StorageSeries(BaseModel):
    charge: list[float]
    discharge: list[float]
    soc: list[float]


# 外网：购电、售电、分时电价
class ExchangeSeries(BaseModel):
    buy: list[float]
    sell: list[float]
    price: list[float]


# 某一天的 24 点时序
class DashboardDay(BaseModel):
    date: str
    hours: list[str]
    balance: BalanceSeries
    wind: RenewableSeries
    pv: RenewableSeries
    storage: StorageSeries
    exchange: ExchangeSeries
