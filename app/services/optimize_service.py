# -*- coding: utf-8 -*-
"""容量优化：PSO 求总成本最小的风光储配置"""

import numpy as np
import pandas as pd

# 设备与成本参数，和仪表盘保持一致
V_CUT_IN = 3.0
V_RATED = 11.0
WIND_PRICE = 6500.0     # 元每 kW
PV_PRICE = 3500.0
BESS_PRICE = 1200.0
RATE = 0.08             # 折现率
YEARS = 20              # 项目年限
SAMPLE_DAYS = 243       # 数据覆盖天数
SOCIETY = 0.92          # 储能效率

# 决策变量上下限 风 光 储功率 储容量
BOUNDS = [(0.0, 200.0), (0.0, 200.0), (0.0, 100.0), (0.0, 400.0)]


def _data(con):
    """读气象、电价与参数，拼成逐时数组"""
    src = pd.read_sql("SELECT ts, wind_speed, ghi, load_mw FROM t_source ORDER BY ts", con)
    tariff = pd.read_sql("SELECT hour, price FROM t_tariff ORDER BY hour", con)
    params = pd.read_sql("SELECT name, value FROM t_param WHERE category = 'cost'", con)
    src["hour"] = pd.to_datetime(src["ts"]).dt.hour
    src = src.merge(tariff, on="hour", how="left")
    return {
        "wind_speed": src["wind_speed"].to_numpy(dtype=float),
        "ghi": src["ghi"].to_numpy(dtype=float),
        "load": src["load_mw"].to_numpy(dtype=float),
        "price": src["price"].fillna(0).to_numpy(dtype=float),
        "cost": {r["name"]: float(r["value"]) for _, r in params.iterrows()},
    }


def _simulate(x, data):
    """给定容量跑逐时调度，返回电量与成本"""
    wind_cap, pv_cap, bess_mw, bess_mwh = [float(v) for v in x]
    v = data["wind_speed"]
    p_wind = np.where(v < V_CUT_IN, 0.0,
                      np.where(v >= V_RATED, wind_cap,
                               wind_cap * ((v - V_CUT_IN) / (V_RATED - V_CUT_IN)) ** 3))
    p_pv = data["ghi"] / 1000.0 * pv_cap * 0.82
    p_re = p_wind + p_pv
    load = data["load"]
    price = data["price"]
    n = len(load)
    soc = 0.5 * bess_mwh
    buy = np.zeros(n)
    curt = np.zeros(n)
    for i in range(n):
        net = load[i] - p_re[i]
        if net > 0:
            dis = min(net, bess_mw, max(0.0, soc - 0.1 * bess_mwh) * SOCIETY)
            soc -= dis / SOCIETY
            buy[i] = net - dis
        else:
            surplus = -net
            ch = min(surplus, bess_mw, max(0.0, 0.95 * bess_mwh - soc) / SOCIETY)
            soc += ch * SOCIETY
            curt[i] = surplus - ch
    return buy, curt, p_re


def _score(x, data):
    """年化总成本，违反弃电率约束加罚"""
    wind_cap, pv_cap, bess_mw, bess_mwh = [float(v) for v in x]
    buy, curt, p_re = _simulate(x, data)
    invest = wind_cap * 1000 * WIND_PRICE / 10000
    invest += pv_cap * 1000 * PV_PRICE / 10000
    invest += bess_mwh * 1000 * BESS_PRICE / 10000
    crf = RATE * (1 + RATE) ** YEARS / ((1 + RATE) ** YEARS - 1)
    annual_invest = invest * crf
    buy_wan = float((buy * data["price"] / 10).sum())
    annual_buy = buy_wan * 365 / SAMPLE_DAYS
    curt_rate = float(curt.sum() / p_re.sum()) if p_re.sum() else 0.0
    penalty = 1e6 * max(0.0, curt_rate - 0.2)
    penalty += 1e6 * max(0.0, bess_mwh - 4.0 * bess_mw)
    return annual_invest + annual_buy + penalty, {
        "invest_wan": round(invest, 1),
        "annual_invest": round(annual_invest, 1),
        "annual_buy": round(annual_buy, 1),
        "annual_cost": round(annual_invest + annual_buy, 1),
        "buy_mwh": round(float(buy.sum()), 1),
        "curt_mwh": round(float(curt.sum()), 1),
        "curt_rate": round(curt_rate * 100, 2),
        "consume_rate": round((1 - curt_rate) * 100, 2),
    }


def _pso(data, popsize=20, iters=40):
    """标准粒子群，含现状解作为初始粒子"""
    rng = np.random.default_rng(0)
    lo = np.array([b[0] for b in BOUNDS])
    hi = np.array([b[1] for b in BOUNDS])
    x = rng.uniform(lo, hi, size=(popsize, len(lo)))
    x[0] = np.array([50.0, 80.0, 20.0, 80.0])
    v = rng.uniform(-1, 1, size=x.shape) * (hi - lo) * 0.1
    pbest = x.copy()
    pbest_score = np.array([_score(p, data)[0] for p in x])
    gbest = pbest[pbest_score.argmin()].copy()
    gbest_score = float(pbest_score.min())
    curve = []
    for _ in range(iters):
        w = 0.9 - 0.5 * _ / iters
        r1 = rng.random(size=x.shape)
        r2 = rng.random(size=x.shape)
        v = w * v + 2.0 * r1 * (pbest - x) + 2.0 * r2 * (gbest - x)
        x = np.clip(x + v, lo, hi)
        scores = np.array([_score(p, data)[0] for p in x])
        better = scores < pbest_score
        pbest[better] = x[better]
        pbest_score[better] = scores[better]
        if scores.min() < gbest_score:
            gbest = x[scores.argmin()].copy()
            gbest_score = float(scores.min())
        curve.append(round(gbest_score, 1))
    return gbest, gbest_score, curve


def optimize(con):
    """返回推荐配置、指标与收敛曲线"""
    data = _data(con)
    best, score, curve = _pso(data)
    _, best_metrics = _score(best, data)
    _, now_metrics = _score(np.array([50.0, 80.0, 20.0, 80.0]), data)
    return {
        "algorithm": "pso",
        "iterations": len(curve),
        "convergence": curve,
        "best": {
            "wind_mw": round(float(best[0]), 1),
            "pv_mw": round(float(best[1]), 1),
            "bess_mw": round(float(best[2]), 1),
            "bess_mwh": round(float(best[3]), 1),
            **best_metrics,
        },
        "current": {
            "wind_mw": 50.0, "pv_mw": 80.0, "bess_mw": 20.0, "bess_mwh": 80.0,
            **now_metrics,
        },
        "bounds": {
            "wind": list(BOUNDS[0]),
            "pv": list(BOUNDS[1]),
            "bess_mw": list(BOUNDS[2]),
            "bess_mwh": list(BOUNDS[3]),
        },
        "assumption": "折现率 8%，年限 20 年，购电成本按 243 天折算为全年，弃电率上限 20%",
    }
