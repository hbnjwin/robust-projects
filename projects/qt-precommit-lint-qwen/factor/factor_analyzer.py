"""
因子分析器：IC/IR 分析、因子合成
"""

import numpy as np


def _rank(arr):
    """计算排名"""
    temp = arr.argsort()
    ranks = np.empty_like(temp, dtype=float)
    ranks[temp] = np.arange(len(arr), dtype=float)
    return ranks


def compute_ic(factor_values, forward_returns):
    """
    计算单期 IC（因子值与未来收益的 Spearman 秩相关系数）

    factor_values: dict {ts_code: factor_value}
    forward_returns: dict {ts_code: return_value}
    返回: float (IC 值) 或 None
    """
    common = set(factor_values.keys()) & set(forward_returns.keys())
    if len(common) < 5:
        return None

    codes = sorted(common)
    fv = np.array([factor_values[c] for c in codes])
    fr = np.array([forward_returns[c] for c in codes])

    mask = ~(np.isnan(fv) | np.isnan(fr))
    fv = fv[mask]
    fr = fr[mask]

    if len(fv) < 5:
        return None

    fv_rank = _rank(fv)
    fr_rank = _rank(fr)

    mean_fv = np.mean(fv_rank)
    mean_fr = np.mean(fr_rank)

    cov = np.sum((fv_rank - mean_fv) * (fr_rank - mean_fr))
    std_fv = np.sqrt(np.sum((fv_rank - mean_fv) ** 2))
    std_fr = np.sqrt(np.sum((fr_rank - mean_fr) ** 2))

    if std_fv == 0 or std_fr == 0:
        return 0.0

    return cov / (std_fv * std_fr)


def compute_ic_series(factor_data, return_data):
    """
    计算 IC 时间序列

    factor_data: {date: {ts_code: value}}
    return_data: {date: {ts_code: return}}
    返回: list of {date, ic}
    """
    ic_series = []
    dates = sorted(set(factor_data.keys()) & set(return_data.keys()))

    for date in dates:
        ic = compute_ic(factor_data[date], return_data[date])
        if ic is not None:
            ic_series.append({"date": date, "ic": ic})

    return ic_series


def compute_ir(ic_series):
    """
    计算 IR = mean(IC) / std(IC)
    """
    if len(ic_series) < 2:
        return 0.0

    ics = np.array([item["ic"] for item in ic_series])
    std = np.std(ics)
    if std == 0:
        return 0.0
    return np.mean(ics) / std


def composite_equal_weight(factor_data_list):
    """
    等权合成多个因子

    factor_data_list: list of {date: {ts_code: value}}
    返回: {date: {ts_code: composite_value}}
    """
    all_dates = set()
    for fd in factor_data_list:
        all_dates.update(fd.keys())

    result = {}
    for date in sorted(all_dates):
        scores = {}
        for fd in factor_data_list:
            if date not in fd:
                continue
            for code, val in fd[date].items():
                if np.isnan(val):
                    continue
                if code not in scores:
                    scores[code] = []
                scores[code].append(val)

        result[date] = {}
        for code, vals in scores.items():
            result[date][code] = np.mean(vals)

    return result


def composite_ic_weight(factor_data_list, ic_values):
    """
    IC 加权合成多个因子

    factor_data_list: list of {date: {ts_code: value}}
    ic_values: list of float (每个因子的 IC 均值)
    返回: {date: {ts_code: composite_value}}
    """
    total_ic = sum(abs(ic) for ic in ic_values)
    if total_ic == 0:
        return composite_equal_weight(factor_data_list)

    weights = [abs(ic) / total_ic for ic in ic_values]

    all_dates = set()
    for fd in factor_data_list:
        all_dates.update(fd.keys())

    result = {}
    for date in sorted(all_dates):
        scores = {}
        for i, fd in enumerate(factor_data_list):
            if date not in fd:
                continue
            for code, val in fd[date].items():
                if np.isnan(val):
                    continue
                if code not in scores:
                    scores[code] = 0.0
                scores[code] += val * weights[i]

        result[date] = scores

    return result
