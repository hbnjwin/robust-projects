"""
每日 ML 因子计算
用 DuckDB 计算最近交易日的因子，输出到 factors_latest.parquet

调度: 15:15, depends_on: ml_data_export
"""

import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from factor_engine.pipeline import FactorPipeline


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    # 计算最近 90 天的因子（窗口函数需要历史数据）
    start = (datetime.now() - timedelta(days=120)).strftime("%Y-%m-%d")

    print(f"[ml_factor_compute] {today}, range: {start} ~ {today}")

    t0 = time.time()
    pipe = FactorPipeline()
    path = pipe.run(
        start_date=start,
        end_date=today,
        norm_method="robust_zscore",
        output_path="data/factors_latest.parquet",
    )
    pipe.close()

    print(f"[ml_factor_compute] Done in {time.time() - t0:.1f}s, output: {path}")


if __name__ == "__main__":
    main()
