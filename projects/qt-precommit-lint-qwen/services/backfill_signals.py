"""
backfill_signals.py — 批量回测生成历史信号文件
复用 ml_signal_generate 的完整推理逻辑，对指定日期逐日生成信号

用法:
  python services/backfill_signals.py              # 最近 20 个交易日（跳过已有）
  python services/backfill_signals.py --days 30
  python services/backfill_signals.py --overwrite  # 覆盖已有信号
"""

import sys
import os
import json
import time
import argparse
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ml.models import BaseModel

MODEL_DIR = "ml/model_store/v1"
FACTORS_PATH = "data/factors_latest.parquet"
REGIME_PATH = "data/regime_labels.parquet"
SIGNAL_DIR = "data/signals"
_SKIP_COLS = {"ts_code", "trade_date", "label_3d", "label_5d", "label_10d"}

LGB_WEIGHT = 0.2
GRU_WEIGHT = 0.2
HIST_WEIGHT = 0.6


def load_lgb_models():
    models = {}
    for name in ["global", "bull", "crisis", "neutral"]:
        pkl = os.path.join(MODEL_DIR, f"{name}.pkl")
        if os.path.exists(pkl):
            models[name.upper()] = BaseModel.load(pkl)
    return models


def predict_one_day(day_df: pd.DataFrame, lgb_models: dict, feature_names: list, date_str: str) -> dict:
    """对单日因子数据做完整三模型集成推理"""
    if day_df.empty:
        return {}

    ts_codes = day_df["ts_code"].values
    X = day_df[feature_names].values.astype(np.float32)
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

    # LGB
    regime = "NEUTRAL"
    model = lgb_models.get(regime, lgb_models.get("GLOBAL"))
    if model is None:
        print(f"    ❌ 无 LGB 模型")
        return {}
    lgb_scores = model.predict(X)
    lgb_map = dict(zip(ts_codes, lgb_scores))

    # GRU
    gru_map = {}
    try:
        from services.gru_signal_generate import gru_predict

        gru_map = gru_predict(date_str=date_str)
    except Exception as e:
        print(f"    GRU failed: {e}")

    # HIST（支持 trade_date 参数）
    hist_map = {}
    try:
        from services.hist_signal_generate import hist_predict

        hist_map = hist_predict(trade_date=date_str)
    except Exception as e:
        print(f"    HIST failed: {e}")

    # 集成
    final = {}
    for code, lgb_s in lgb_map.items():
        has_gru = code in gru_map
        has_hist = code in hist_map
        if has_gru and has_hist:
            final[code] = LGB_WEIGHT * lgb_s + GRU_WEIGHT * gru_map[code] + HIST_WEIGHT * hist_map[code]
        elif has_hist:
            final[code] = (LGB_WEIGHT + GRU_WEIGHT) * lgb_s + HIST_WEIGHT * hist_map[code]
        elif has_gru:
            final[code] = LGB_WEIGHT * lgb_s + (GRU_WEIGHT + HIST_WEIGHT) * gru_map[code]
        else:
            final[code] = lgb_s

    gru_cov = len([c for c in ts_codes if c in gru_map])
    hist_cov = len([c for c in ts_codes if c in hist_map])
    print(f"    GRU={gru_cov}/{len(ts_codes)} HIST={hist_cov}/{len(ts_codes)}", end="")
    return final


def run(days: int = 20, min_stocks: int = 10000, overwrite: bool = False):
    print(f"\n{'=' * 60}")
    print(f"历史信号回填 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'=' * 60}")

    # 加载因子
    print(f"\n加载因子文件...")
    t0 = time.time()
    df = pd.read_parquet(FACTORS_PATH)
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.strftime("%Y-%m-%d")
    print(f"  {len(df):,} 行, {df['trade_date'].nunique()} 个交易日 ({time.time() - t0:.1f}s)")

    # 确定目标日期（股票数足够的）
    date_counts = df.groupby("trade_date").size()
    all_dates = sorted(date_counts[date_counts >= min_stocks].index.tolist())
    target_dates = all_dates[-days:]

    # 跳过已有信号
    signal_dir = Path(SIGNAL_DIR)
    signal_dir.mkdir(exist_ok=True)
    if not overwrite:
        existing = {f.stem for f in signal_dir.glob("*.json")}
        skip = [d for d in target_dates if d in existing]
        target_dates = [d for d in target_dates if d not in existing]
        if skip:
            print(f"  跳过已有: {skip}")

    print(f"  需要生成: {len(target_dates)} 个日期")
    if not target_dates:
        print("  无需回填")
        return

    # 加载模型
    print(f"\n加载 LGB 模型...")
    lgb_models = load_lgb_models()
    print(f"  已加载: {list(lgb_models.keys())}")

    meta_path = os.path.join(MODEL_DIR, "meta.json")
    with open(meta_path) as f:
        meta = json.load(f)
    feature_names = meta.get("feature_names", [])
    if not feature_names:
        feature_names = [c for c in df.columns if c not in _SKIP_COLS]
    print(f"  特征数: {len(feature_names)}")

    # 逐日推理
    print(f"\n开始逐日推理...")
    success = 0
    for i, date_str in enumerate(target_dates):
        day_df = df[df["trade_date"] == date_str].copy()
        n = len(day_df)
        print(f"  [{i + 1}/{len(target_dates)}] {date_str} ({n} 只) ", end="", flush=True)
        t1 = time.time()

        scores = predict_one_day(day_df, lgb_models, feature_names, date_str)
        if not scores:
            print(f" → ❌")
            continue

        signal_list = sorted(scores.items(), key=lambda x: -x[1])
        signal = {
            "date": date_str,
            "regime": "NEUTRAL",
            "model": f"LGB×{LGB_WEIGHT}+GRU×{GRU_WEIGHT}+HIST×{HIST_WEIGHT}",
            "top_signals": [{"ts_code": c, "score": round(float(s), 6)} for c, s in signal_list[:30]],
            "all_signals": {c: round(float(s), 6) for c, s in signal_list},
        }
        out = signal_dir / f"{date_str}.json"
        out.write_text(json.dumps(signal, ensure_ascii=False))

        print(f" → ✅ {len(scores)} 信号 ({time.time() - t1:.1f}s)")
        success += 1

    print(f"\n{'=' * 60}")
    print(f"完成: {success}/{len(target_dates)} 个日期")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=20)
    parser.add_argument("--min-stocks", type=int, default=10000)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    run(days=args.days, min_stocks=args.min_stocks, overwrite=args.overwrite)
