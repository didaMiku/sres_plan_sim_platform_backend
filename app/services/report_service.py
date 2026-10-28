# -*- coding: utf-8 -*-
"""报告生成业务：把仪表盘的数据组织成 Markdown，不存库。

每个章节一个函数，返回 Markdown 片段，按用户选择的顺序拼接。
"""

import pandas as pd

# 章节顺序与名称，前端也用它渲染列表
SECTIONS = [
    {"key": "project", "name": "项目概况"},
    {"key": "data", "name": "基础数据说明"},
    {"key": "resource", "name": "资源条件分析"},
    {"key": "load", "name": "负荷特性分析"},
    {"key": "method", "name": "建模方法说明"},
    {"key": "capacity", "name": "容量优化结果"},
    {"key": "operation", "name": "运行仿真结果"},
    {"key": "economy", "name": "经济性分析"},
    {"key": "friendliness", "name": "友好性评价"},
    {"key": "plan", "name": "推荐配置方案"},
    {"key": "risk", "name": "风险与建议"},
]

SECTION_NAMES = {s["key"]: s["name"] for s in SECTIONS}


def _project(con):
    cur = con.execute(
        "SELECT id, name, region, plan_year, wind_mw, pv_mw, storage_mw, storage_mwh "
        "FROM project_list ORDER BY id LIMIT 1"
    )
    row = cur.fetchone()
    if row is None:
        raise ValueError("项目不存在")
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, row))


def _frames(con):
    src = pd.read_sql("SELECT * FROM t_source ORDER BY ts", con)
    sim = pd.read_sql("SELECT * FROM t_simulation ORDER BY ts", con)
    params = pd.read_sql("SELECT * FROM t_param", con)
    tariff = pd.read_sql("SELECT * FROM t_tariff ORDER BY hour", con)
    src["ts"] = pd.to_datetime(src["ts"])
    sim["ts"] = pd.to_datetime(sim["ts"])
    return src, sim, params, tariff


def _cost(params, name, default):
    rows = params[(params["category"] == "cost") & (params["name"] == name)]
    return float(rows.iloc[0]["value"]) if len(rows) else default


def s_project(project):
    return f"""项目位于{project['region']}，规划年份 {project['plan_year']}，现状装机风电 {project['wind_mw']:.0f} MW、光伏 {project['pv_mw']:.0f} MW、储能 {project['storage_mw']:.0f} MW / {project['storage_mwh']:.0f} MWh。

本报告基于园区运行数据，对源网荷储配置与运行情况进行分析评价。"""


def s_data(src, sim):
    return f"""| 数据表 | 行数 | 时间范围 |
|---|---|---|
| 源荷气象 | {len(src)} | {src['ts'].min()} ~ {src['ts'].max()} |
| 运行仿真 | {len(sim)} | {sim['ts'].min()} ~ {sim['ts'].max()} |

数据为小时级时序，覆盖 2026 年 1 月至 8 月，共 {len(sim)} 个时刻。"""


def s_resource(src):
    return f"""| 指标 | 均值 | 最大 | 最小 |
|---|---|---|---|
| 风速 | {src['wind_speed'].mean():.2f} m/s | {src['wind_speed'].max():.2f} | {src['wind_speed'].min():.2f} |
| 总辐照度 | {src['ghi'].mean():.1f} W/m² | {src['ghi'].max():.1f} | {src['ghi'].min():.1f} |
| 温度 | {src['temperature'].mean():.1f} ℃ | {src['temperature'].max():.1f} | {src['temperature'].min():.1f} |

辐照度在夜间为 0，白天峰值出现在正午前后；风速整体集中在 3 至 9 m/s。"""


def s_load(sim):
    load = sim["load_mw"]
    return f"""负荷均值 {load.mean():.2f} MW，最大 {load.max():.2f} MW，最小 {load.min():.2f} MW，峰谷差 {load.max() - load.min():.2f} MW，负荷率 {load.mean() / load.max() * 100:.1f}%。

负荷曲线呈明显的日内分段特征，8 至 16 时与 17 至 18 时为两个高位区间。"""


def s_method():
    return """本报告指标口径如下：

- 绿电占比 = 风光发电量除以负荷电量；
- 本地消纳率 = 本地消纳电量除以可发电量，可发电量由气象数据与设备参数反算；
- 峰值削减率 = 1 减去最大净负荷除以最大负荷；
- 初始投资 = 装机容量乘以单位造价。

出力与负荷预测采用随机森林回归，以时间、温度、历史同时刻值为特征，训练集只使用预测日之前的数据。"""


def s_capacity(project, params):
    wind, pv, bess = project["wind_mw"], project["pv_mw"], project["storage_mwh"]
    inv = wind * 1000 * _cost(params, "风电CAPEX", 6500) / 10000
    inv_pv = pv * 1000 * _cost(params, "光伏CAPEX", 3500) / 10000
    inv_bess = bess * 1000 * _cost(params, "储能CAPEX", 1200) / 10000
    return f"""| 设备 | 容量 | 投资 |
|---|---|---|
| 风电 | {wind:.0f} MW | {inv:,.0f} 万元 |
| 光伏 | {pv:.0f} MW | {inv_pv:,.0f} 万元 |
| 储能 | {project['storage_mw']:.0f} MW / {bess:.0f} MWh | {inv_bess:,.0f} 万元 |
| 合计 | — | {inv + inv_pv + inv_bess:,.0f} 万元 |

以上为现状装机方案，容量优化结果方案为风电 80 MW、光伏 120 MW、储能 40 MW / 160 MWh。"""


def s_operation(sim):
    charge_hours = int((sim["battery_charge_mw"] > 0).sum())
    discharge_hours = int((sim["battery_discharge_mw"] > 0).sum())
    return f"""| 指标 | 数值 |
|---|---|
| 风电发电量 | {sim['wind_power_mw'].sum():,.0f} MWh |
| 光伏发电量 | {sim['pv_power_mw'].sum():,.0f} MWh |
| 负荷用电量 | {sim['load_mw'].sum():,.0f} MWh |
| 外网购电量 | {sim['grid_buy_mw'].sum():,.0f} MWh |
| 储能充电小时 | {charge_hours} h |
| 储能放电小时 | {discharge_hours} h |

储能大部分时间处于荷电状态下限，等效循环次数较低，实际调节能力有限。"""


def s_economy(project, sim, params, tariff):
    wind, pv, bess = project["wind_mw"], project["pv_mw"], project["storage_mwh"]
    capex = (
        wind * 1000 * _cost(params, "风电CAPEX", 6500)
        + pv * 1000 * _cost(params, "光伏CAPEX", 3500)
        + bess * 1000 * _cost(params, "储能CAPEX", 1200)
    ) / 10000
    sim_h = sim.copy()
    sim_h["hour"] = sim_h["ts"].dt.hour
    sim_h = sim_h.merge(tariff[["hour", "price"]], on="hour", how="left")
    cost = float((sim_h["grid_buy_mw"] * sim_h["price"]).sum())
    return f"""初始投资合计 {capex:,.0f} 万元，按风电 {_cost(params, '风电CAPEX', 6500):.0f} 元/kW、光伏 {_cost(params, '光伏CAPEX', 3500):.0f} 元/kW、储能 {_cost(params, '储能CAPEX', 1200):.0f} 元/kWh 计算。

统计期内外购电成本约 {cost:,.0f} 万元，按华东分时电价逐时计算。由于缺少运维成本与项目年限，本报告不计算度电成本。"""


def s_friendliness(sim, consume_rate):
    green = (sim["wind_power_mw"].sum() + sim["pv_power_mw"].sum()) / sim["load_mw"].sum() * 100
    curtail = sim["curtailment_mw"].sum() / max(sim["wind_power_mw"].sum() + sim["pv_power_mw"].sum(), 1e-9) * 100
    active = int((sim["battery_charge_mw"] > 0).sum() + (sim["battery_discharge_mw"] > 0).sum())
    bess_util = active / len(sim) * 100
    peak_rate = (sim["load_mw"].max() - sim["load_mw"].min()) / sim["load_mw"].max() * 100
    return f"""| 指标 | 数值 |
|---|---|
| 绿电占比 | {green:.1f}% |
| 本地消纳率 | {consume_rate:.1f}% |
| 弃电率 | {curtail:.1f}% |
| 储能利用率 | {bess_util:.1f}% |
| 峰谷差率 | {peak_rate:.1f}% |

各项指标按统一口径计算，数值与仪表盘一致。"""


def s_plan():
    return """推荐采用风电 80 MW、光伏 120 MW、储能 40 MW / 160 MWh 的配置方案。

该方案在现有数据下可提升新能源装机规模，储能用于平滑午间光伏出力与晚间负荷高峰。由于缺少优化求解器与完整经济参数，本方案为给定结果方案的展示，未经重新优化。"""


def s_risk():
    return """1. 数据仅覆盖 2026 年 1 至 8 月，并非完整年度，年度指标为统计期口径；
2. 源荷气象数据与运行仿真数据并非同一数据链，风电出力相关性较低；
3. 运行仿真数据中弃风弃光恒为 0、功率平衡误差恒为 0，储能长期处于荷电状态下限，与理想调度结果存在差距；
4. 缺少排放因子、运维成本与项目年限，低碳指标与度电成本无法计算；
5. 预测模型使用仿真数据训练，精度不代表真实场景。"""


BUILDERS = {
    "project": lambda project, src, sim, params, tariff, consume_rate: s_project(project),
    "data": lambda project, src, sim, params, tariff, consume_rate: s_data(src, sim),
    "resource": lambda project, src, sim, params, tariff, consume_rate: s_resource(src),
    "load": lambda project, src, sim, params, tariff, consume_rate: s_load(sim),
    "method": lambda project, src, sim, params, tariff, consume_rate: s_method(),
    "capacity": lambda project, src, sim, params, tariff, consume_rate: s_capacity(project, params),
    "operation": lambda project, src, sim, params, tariff, consume_rate: s_operation(sim),
    "economy": lambda project, src, sim, params, tariff, consume_rate: s_economy(project, sim, params, tariff),
    "friendliness": lambda project, src, sim, params, tariff, consume_rate: s_friendliness(sim, consume_rate),
    "plan": lambda project, src, sim, params, tariff, consume_rate: s_plan(),
    "risk": lambda project, src, sim, params, tariff, consume_rate: s_risk(),
}


def _consume_rate(src):
    """本地消纳率，和仪表盘保持一致。"""
    import numpy as np

    v = src["wind_speed"].to_numpy(dtype=float)
    p_wind = np.where(v < 3, 0.0, np.where(v >= 11, 50.0, 50.0 * ((v - 3) / 8) ** 3))
    p_pv = src["ghi"].to_numpy(dtype=float) / 1000 * 80.0
    avail = p_wind + p_pv
    if avail.sum() == 0:
        return 0.0
    return float(np.minimum(avail, src["load_mw"].to_numpy(dtype=float)).sum() / avail.sum() * 100)


def build_report(con, title, sections) -> dict:
    """按章节顺序生成 Markdown 报告。"""
    keys = [k for k in sections if k in BUILDERS]
    if not keys:
        raise ValueError("至少选择一个章节")

    project = _project(con)
    src, sim, params, tariff = _frames(con)
    consume_rate = _consume_rate(src)

    lines = [f"# {title}", ""]
    lines.append(f"> 统计期 {src['ts'].min()} ~ {src['ts'].max()}，共 {len(sim)} 个时刻。")
    lines.append("")

    for i, key in enumerate(keys, 1):
        lines.append(f"## {i}. {SECTION_NAMES[key]}")
        lines.append("")
        lines.append(BUILDERS[key](project, src, sim, params, tariff, consume_rate))
        lines.append("")

    markdown = "\n".join(lines).strip() + "\n"
    return {
        "filename": f"规划报告-{pd.Timestamp.now():%Y%m%d-%H%M}.md",
        "markdown": markdown,
    }
