"""
因子加载器：从 PostgreSQL factor_values 表加载预计算因子
"""
import psycopg
import sys
sys.path.insert(0, "/home/tulin/quant")
from config import PG_CONFIG

FACTOR_NAMES = {
    1: "MA_DIFF_5_21",
    2: "MOM_60",
    3: "VOL_20",
    4: "VOL_RATIO_20"
}

FACTOR_IDS = {v: k for k, v in FACTOR_NAMES.items()}


def load_factors(start_date, end_date, factor_names=None, ts_codes=None):
    """
    从 factor_values 表加载因子数据。
    返回: {date_str: {ts_code: {factor_name: value}}}
    """
    conn = psycopg.connect(**PG_CONFIG)

    conditions = ["trade_date BETWEEN %s AND %s"]
    params = [start_date, end_date]

    if factor_names:
        fids = [FACTOR_IDS[n] for n in factor_names if n in FACTOR_IDS]
        if fids:
            placeholders = ",".join(["%s"] * len(fids))
            conditions.append("factor_id IN (" + placeholders + ")")
            params.extend(fids)

    if ts_codes:
        placeholders = ",".join(["%s"] * len(ts_codes))
        conditions.append("ts_code IN (" + placeholders + ")")
        params.extend(ts_codes)

    where = " AND ".join(conditions)
    query = "SELECT trade_date, ts_code, factor_id, value FROM factor_values WHERE " + where + " ORDER BY trade_date"

    cur = conn.cursor()
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    result = {}
    for trade_date, ts_code, factor_id, value in rows:
        date_str = str(trade_date)
        if date_str not in result:
            result[date_str] = {}
        if ts_code not in result[date_str]:
            result[date_str][ts_code] = {}
        fname = FACTOR_NAMES.get(factor_id, "factor_" + str(factor_id))
        result[date_str][ts_code][fname] = float(value)

    return result
