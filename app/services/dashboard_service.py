# -*- coding: utf-8 -*-
"""仪表盘接口业务实现
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import (
    mean_absolute_error,
    mean_absolute_percentage_error,
    mean_squared_error,
    r2_score,
)

# 设备参数来自 t_param 和 02 文件，集中放这里
WIND_CAP_MW = 50.0
PV_CAP_MW = 80.0
V_CUT_IN = 3.0
V_RATED = 11.0
PV_KWH_PER_GHI = PV_CAP_MW / 1000.0  # GHI 乘这个系数得到光伏 MW
DEFAULT_DAY = "2026-01-24"           # 缺省展示的日期，储能动作最多


def _load_frames(con):
    """一次读出仪表盘需要的四张表。"""
    sim = pd.read_sql("SELECT * FROM t_simulation ORDER BY ts", con)
    src = pd.read_sql("SELECT * FROM t_source ORDER BY ts", con)
    tariff = pd.read_sql("SELECT * FROM t_tariff ORDER BY hour", con)
    params = pd.read_sql("SELECT * FROM t_param", con)
    sim["ts"] = pd.to_datetime(sim["ts"])
    src["ts"] = pd.to_datetime(src["ts"])
    return sim, src, tariff, params


def _project(con, project_id=None):
    """缺省取数据库第一条"""
    sql = (
        "SELECT id, name, region, plan_year, wind_mw, pv_mw, storage_mw, storage_mwh "
        "FROM project_list "
    )
    if project_id is None:
        row = con.execute(sql + "ORDER BY id LIMIT 1").fetchone()
    else:
        row = con.execute(sql + "WHERE id = ?", (project_id,)).fetchone()
    if row is None:
        raise ValueError("项目不存在")
    return dict(row)


def _capital_cost(project, params) -> float:
    """初始投资，单位万元"""
    cost = {
        r["name"]: float(r["value"])
        for _, r in params[params["category"] == "cost"].iterrows()
    }
    wind = project["wind_mw"] * 1000 * cost.get("风电CAPEX", 6500) / 10000
    pv = project["pv_mw"] * 1000 * cost.get("光伏CAPEX", 3500) / 10000
    bess = project["storage_mwh"] * 1000 * cost.get("储能CAPEX", 1200) / 10000
    return round(wind + pv + bess, 1)


def summary(con, project_id=None) -> dict:
    """顶部 KPI、底部指标卡、指标条"""
    project = _project(con, project_id)
    sim, src, tariff, params = _load_frames(con)

    # 能量流
    e_wind = float(sim["wind_power_mw"].sum())
    e_pv = float(sim["pv_power_mw"].sum())
    e_load = float(sim["load_mw"].sum())
    e_buy = float(sim["grid_buy_mw"].sum())
    e_curt = float(sim["curtailment_mw"].sum())

    green_ratio = (e_wind + e_pv) / e_load * 100 if e_load else 0.0

    # 本地消纳率，用 03 气象和 02 参数反算
    v = src["wind_speed"].to_numpy(dtype=float)
    p_wind = np.where(
        v < V_CUT_IN,
        0.0,
        np.where(v >= V_RATED, WIND_CAP_MW, WIND_CAP_MW * ((v - V_CUT_IN) / (V_RATED - V_CUT_IN)) ** 3),
    )
    p_pv = src["ghi"].to_numpy(dtype=float) * PV_KWH_PER_GHI
    avail = p_wind + p_pv
    load_src = src["load_mw"].to_numpy(dtype=float)
    consume_rate = float(np.minimum(avail, load_src).sum() / avail.sum() * 100) if avail.sum() else 0.0

    # 峰值削减率
    net = sim["load_mw"] - sim["wind_power_mw"] - sim["pv_power_mw"]
    peak_cut = float((1 - net.max() / sim["load_mw"].max()) * 100) if sim["load_mw"].max() else 0.0

    # 储能利用率
    active_hours = int((sim["battery_charge_mw"] > 0).sum() + (sim["battery_discharge_mw"] > 0).sum())
    bess_util = active_hours / len(sim) * 100 if len(sim) else 0.0

    # 购电成本，按 07 分时电价
    sim_h = sim.copy()
    sim_h["hour"] = sim_h["ts"].dt.hour
    sim_h = sim_h.merge(tariff[["hour", "price"]], on="hour", how="left")
    buy_cost = float((sim_h["grid_buy_mw"] * sim_h["price"]).sum())

    # 峰谷
    peak = float(sim["load_mw"].max())
    valley = float(sim["load_mw"].min())
    peak_valley = peak - valley
    peak_valley_rate = peak_valley / peak * 100 if peak else 0.0

    capex = _capital_cost(project, params)
    curtail_rate = e_curt / (e_wind + e_pv) * 100 if (e_wind + e_pv) else 0.0

    return {
        "project": project,
        "kpi": [
            {"key": "green_ratio", "label": "绿电占比", "en": "Green Ratio",
             "value": round(green_ratio, 2), "unit": "%",
             "caliber": "风光发电量除以负荷电量"},
            {"key": "consume_rate", "label": "本地消纳率", "en": "RE Utilization",
             "value": round(consume_rate, 2), "unit": "%",
             "caliber": "本地消纳电量除以可发电量，用 03 气象和 02 参数反算"},
            {"key": "peak_cut", "label": "峰值削减率", "en": "Peak Shaving",
             "value": round(peak_cut, 2), "unit": "%",
             "caliber": "1 减去最大净负荷除以最大负荷"},
            {"key": "capex", "label": "初始投资", "en": "CAPEX",
             "value": capex, "unit": "万元",
             "caliber": "装机乘以 t_param 单价"},
        ],
        "cards": [
            {"key": "wind_mw", "label": "风电装机", "value": project["wind_mw"], "unit": "MW"},
            {"key": "pv_mw", "label": "光伏装机", "value": project["pv_mw"], "unit": "MW"},
            {"key": "storage", "label": "储能功率 / 容量",
             "value": f"{project['storage_mw']:.0f} MW / {project['storage_mwh']:.0f} MWh", "unit": ""},
            {"key": "buy_mwh", "label": "外网购电量", "value": round(e_buy, 1), "unit": "MWh"},
            {"key": "buy_cost", "label": "购电成本 1–8 月", "value": round(buy_cost, 1), "unit": "万元"},
            {"key": "peak_valley", "label": "峰谷差", "value": round(peak_valley, 2), "unit": "MW"},
        ],
        "indicators": [
            {"key": "green_ratio", "label": "绿电占比", "value": round(green_ratio, 1), "unit": "%"},
            {"key": "consume_rate", "label": "本地消纳率", "value": round(consume_rate, 1), "unit": "%"},
            {"key": "curtail_rate", "label": "弃电率", "value": round(curtail_rate, 1), "unit": "%"},
            {"key": "bess_util", "label": "储能利用率", "value": round(bess_util, 1), "unit": "%"},
            {"key": "peak_valley_rate", "label": "峰谷差率", "value": round(peak_valley_rate, 1), "unit": "%"},
        ],
        "meta": {
            "data_start": str(sim["ts"].min()),
            "data_end": str(sim["ts"].max()),
            "hours": int(len(sim)),
            # 默认展示的日期
            "default_day": DEFAULT_DAY,
        },
    }


def day(con, date=None) -> dict:
    """某一天的 24 点时序，供平衡图、出力图、储能图、外网图共用。"""
    day_text = date or DEFAULT_DAY
    sim = pd.read_sql(
        "SELECT * FROM t_simulation WHERE ts LIKE ? ORDER BY ts",
        con,
        params=(f"{day_text} %",),
    )
    if sim.empty:
        raise ValueError(f"日期 {day_text} 没有运行数据")

    tariff = pd.read_sql("SELECT hour, price FROM t_tariff ORDER BY hour", con)
    sim["ts"] = pd.to_datetime(sim["ts"])
    sim["hour"] = sim["ts"].dt.hour
    sim = sim.merge(tariff, on="hour", how="left")

    def col(name):
        """转成保留三位小数的普通列表。"""
        return [round(float(v), 3) for v in sim[name]]

    return {
        "date": day_text,
        "hours": sim["ts"].dt.strftime("%H:%M").tolist(),
        "balance": {
            "wind": col("wind_power_mw"),
            "pv": col("pv_power_mw"),
            "discharge": col("battery_discharge_mw"),
            "buy": col("grid_buy_mw"),
            "load": col("load_mw"),
        },
        "wind": {"actual": col("wind_power_mw"), "capacity": WIND_CAP_MW},
        "pv": {"actual": col("pv_power_mw"), "capacity": PV_CAP_MW},
        "storage": {
            "charge": col("battery_charge_mw"),
            "discharge": col("battery_discharge_mw"),
            "soc": col("soc"),
        },
        "exchange": {
            "buy": col("grid_buy_mw"),
            "sell": col("grid_sell_mw"),
            "price": col("price"),
        },
    }


def day_15(con, date=None) -> dict:
    """某一天的 15 分钟时序，数据来自 t_typical_day。

    没有数据时返回 available 为 false，不抛异常，前端显示空态。
    """
    if date is None:
        row = con.execute("SELECT MIN(ts) FROM t_typical_day").fetchone()
        date = row[0][:10] if row and row[0] else None
    if date is None:
        return {"date": "", "resolution": "15m", "available": False, "points": []}

    td = pd.read_sql(
        "SELECT * FROM t_typical_day WHERE ts LIKE ? ORDER BY ts",
        con,
        params=(f"{date} %",),
    )
    if td.empty:
        return {"date": date, "resolution": "15m", "available": False, "points": []}

    td["ts"] = pd.to_datetime(td["ts"])
    points = []
    for _, r in td.iterrows():
        pv = round(float(r["pv_available_mw"]), 3)
        load = round(float(r["load_mw"]), 3)
        points.append({
            "ts": r["ts"].strftime("%H:%M"),
            "pv": pv,
            "load": load,
            "net": round(load - pv, 3),
        })

    return {
        "date": date,
        "resolution": "15m",
        "available": True,
        "points": points,
    }


# 三个预测目标：数据表、标签列、气象特征列、中文名
FORECAST_TARGETS = {
    "load": {"table": "t_source", "label": "load_mw", "weather": "temperature", "name": "负荷"},
    "wind": {"table": "t_simulation", "label": "wind_power_mw", "weather": "wind_speed", "name": "风电出力"},
    "pv": {"table": "t_simulation", "label": "pv_power_mw", "weather": "ghi", "name": "光伏出力"},
}


def forecast(con, date=None, target="load") -> dict:
    """负荷、风电、光伏预测，用随机森林回归。

    用请求日期之前的历史数据训练，预测该日期当天的 24 点。
    日期之前不足 7 天数据时拒绝预测。
    """
    cfg = FORECAST_TARGETS.get(target)
    if cfg is None:
        raise ValueError("不支持的预测目标")

    sql = f"SELECT ts, {cfg['label']} AS y, {cfg['weather']} AS weather FROM {cfg['table']} ORDER BY ts"
    src = pd.read_sql(sql, con)
    src["ts"] = pd.to_datetime(src["ts"])

    df = src.copy()
    df["hour"] = df["ts"].dt.hour
    df["weekday"] = df["ts"].dt.weekday
    df["month"] = df["ts"].dt.month
    # 昨日同一时刻的值，预测当天时这个值已知
    df["lag24"] = df["y"].shift(24)
    df = df.dropna(subset=["lag24"]).reset_index(drop=True)

    day_text = date or df["ts"].dt.strftime("%Y-%m-%d").max()
    day_start = pd.Timestamp(day_text)
    day_end = day_start + pd.Timedelta(days=1)

    train = df[df["ts"] < day_start]
    day_df = df[(df["ts"] >= day_start) & (df["ts"] < day_end)]
    if len(train) < 24 * 7:
        raise ValueError("该日期之前不足 7 天数据，无法训练")
    if day_df.empty:
        raise ValueError("该日期没有运行数据")

    features = ["hour", "weekday", "month", "weather", "lag24"]
    model = RandomForestRegressor(n_estimators=120, max_depth=12, random_state=0, n_jobs=-1)
    model.fit(train[features].to_numpy(), train["y"].to_numpy())
    pred = model.predict(day_df[features].to_numpy())

    actual = day_df["y"].to_numpy()
    mae = mean_absolute_error(actual, pred)
    rmse = mean_squared_error(actual, pred) ** 0.5
    mape = mean_absolute_percentage_error(actual, pred) * 100
    r2 = r2_score(actual, pred)

    return {
        "target": target,
        "target_name": cfg["name"],
        "date": day_text,
        "hours": day_df["ts"].dt.strftime("%H:%M").tolist(),
        "actual": [round(float(v), 3) for v in actual],
        "predicted": [round(float(v), 3) for v in pred],
        "model": "RandomForestRegressor",
        "metrics": {
            "mae": round(float(mae), 3),
            "rmse": round(float(rmse), 3),
            "mape": round(float(mape), 2),
            "r2": round(float(r2), 3),
        },
        "train_start": str(train["ts"].min()),
        "train_end": str(train["ts"].max()),
        "train_rows": int(len(train)),
        "placeholder": False,
    }
