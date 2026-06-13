"""
腾讯实时行情 API 封装
免费，无需 key，支持批量查询（一次最多 50 只）

用法:
    from services.realtime_quotes import get_realtime_quotes
    quotes = get_realtime_quotes(["000001.SZ", "600000.SH"])
"""
import urllib.request
from datetime import datetime


# ts_code → 腾讯代码
def _to_tencent(ts_code: str) -> str:
    symbol, exchange = ts_code.split(".")
    if exchange == "SH":
        return f"sh{symbol}"
    elif exchange == "SZ":
        return f"sz{symbol}"
    elif exchange == "BJ":
        return f"bj{symbol}"
    return ts_code


def get_realtime_quotes(ts_codes: list[str], timeout: int = 10) -> dict:
    """
    批量获取实时行情

    返回: {ts_code: {name, price, change_pct, volume, high, low, open, pre_close, amount, bid1, ask1, time}}
    """
    if not ts_codes:
        return {}

    results = {}
    # 每批最多 50 只
    for i in range(0, len(ts_codes), 50):
        batch = ts_codes[i:i + 50]
        tencent_codes = [_to_tencent(c) for c in batch]
        url = f"http://qt.gtimg.cn/q={','.join(tencent_codes)}"

        try:
            req = urllib.request.Request(url)
            resp = urllib.request.urlopen(req, timeout=timeout)
            data = resp.read().decode("gbk")
        except Exception as e:
            print(f"[quotes] Error fetching batch {i}: {e}")
            continue

        for line in data.strip().split(";"):
            line = line.strip()
            if not line or "=" not in line:
                continue

            key, val = line.split("=", 1)
            fields = val.strip('"').split("~")
            if len(fields) < 45:
                continue

            # 还原 ts_code
            market = fields[0]
            symbol = fields[2]
            if market == "51":
                ts_code = f"{symbol}.SZ"
            elif market == "1":
                ts_code = f"{symbol}.SH"
            elif market == "":
                # BJ
                ts_code = f"{symbol}.BJ"
            else:
                ts_code = f"{symbol}.{market}"

            try:
                price = float(fields[3]) if fields[3] else 0
                pre_close = float(fields[4]) if fields[4] else 0
                open_price = float(fields[5]) if fields[5] else 0
                volume = float(fields[6]) if fields[6] else 0
                change_pct = float(fields[32]) if fields[32] else 0
                high = float(fields[33]) if fields[33] else 0
                low = float(fields[34]) if fields[34] else 0
                amount = float(fields[37]) if fields[37] else 0  # 万元

                results[ts_code] = {
                    "name": fields[1],
                    "price": price,
                    "pre_close": pre_close,
                    "open": open_price,
                    "high": high,
                    "low": low,
                    "volume": volume,
                    "amount": amount,
                    "change_pct": change_pct,
                    "time": fields[30] if len(fields) > 30 else "",
                }
            except (ValueError, IndexError):
                continue

    return results


if __name__ == "__main__":
    codes = ["000001.SZ", "600000.SH", "300750.SZ", "000004.SZ"]
    quotes = get_realtime_quotes(codes)
    for code, q in quotes.items():
        print(f"{code} {q['name']:8s} 现价={q['price']:>8.2f} 涨跌={q['change_pct']:>+6.2f}% 成交={q['volume']:>10.0f}")
