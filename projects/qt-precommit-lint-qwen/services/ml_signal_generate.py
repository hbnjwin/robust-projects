"""
每日 ML 信号生成
加载最新因子 + 训练好的模型 → 生成当日交易信号

调度: 15:20, depends_on: ml_factor_compute
输出: data/signals/YYYY-MM-DD.json (兼容 paper_trading_v1)
"""

import sys
import os
import json
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ml.models import BaseModel

MODEL_DIR = "ml/model_store/v1"
FACTORS_PATH = "data/factors_latest.parquet"
REGIME_PATH = "data/regime_labels.parquet"
SIGNAL_DIR = "data/signals"

# 因子列（排除元数据和标签）
_SKIP_COLS = {"ts_code", "trade_date", "label_3d", "label_5d", "label_10d"}


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"[ml_signal_generate] {today}")

    os.makedirs(SIGNAL_DIR, exist_ok=True)

    # 1. 加载模型
    t0 = time.time()
    models = {}
    for name in ["global", "bull", "crisis", "neutral"]:
        pkl = os.path.join(MODEL_DIR, f"{name}.pkl")
        if os.path.exists(pkl):
            models[name.upper()] = BaseModel.load(pkl)

    meta_path = os.path.join(MODEL_DIR, "meta.json")
    with open(meta_path) as f:
        meta = json.load(f)
    feature_names = meta.get("feature_names", [])
    print(f"  Models loaded: {list(models.keys())} ({time.time() - t0:.1f}s)")

    # 2. 加载最新因子
    t1 = time.time()
    df = pd.read_parquet(FACTORS_PATH)
    df["trade_date"] = pd.to_datetime(df["trade_date"])

    # 取最新交易日
    latest_date = df["trade_date"].max()
    latest_str = latest_date.strftime("%Y-%m-%d")
    day_df = df[df["trade_date"] == latest_date]
    print(f"  Latest date: {latest_str}, {len(day_df)} stocks ({time.time() - t1:.1f}s)")

    if day_df.empty:
        print("  [WARN] No data for latest date, aborting.")
        return

    # 3. 确定 Regime
    regime = "NEUTRAL"
    if os.path.exists(REGIME_PATH):
        regime_df = pd.read_parquet(REGIME_PATH)
        regime_df["trade_date"] = pd.to_datetime(regime_df["trade_date"])
        match = regime_df[regime_df["trade_date"] == latest_date]
        if not match.empty:
            regime = match.iloc[0]["regime"]
    print(f"  Regime: {regime}")

    # 4. LGB 预测
    model = models.get(regime, models.get("GLOBAL"))
    if model is None:
        print("  [ERROR] No model available")
        return

    if not feature_names:
        feature_names = [c for c in day_df.columns if c not in _SKIP_COLS]

    X = day_df[feature_names].values.astype(np.float32)
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    lgb_scores = model.predict(X)
    ts_codes = day_df["ts_code"].values
    lgb_score_map = dict(zip(ts_codes, lgb_scores))

    # 5. GRU + HIST 预测（三模型集成）
    LGB_WEIGHT = 0.2
    GRU_WEIGHT = 0.2
    HIST_WEIGHT = 0.6

    try:
        from services.gru_signal_generate import gru_predict

        gru_score_map = gru_predict()
        print(f"  GRU scores: {len(gru_score_map)} stocks")
    except Exception as e:
        print(f"  [WARN] GRU predict failed: {e}")
        gru_score_map = {}

    try:
        from services.hist_signal_generate import hist_predict

        hist_score_map = hist_predict()
        print(f"  HIST scores: {len(hist_score_map)} stocks")
    except Exception as e:
        print(f"  [WARN] HIST predict failed: {e}")
        hist_score_map = {}

    # 集成：按可用模型动态分配权重
    final_scores = {}
    for code, lgb_s in lgb_score_map.items():
        has_gru = code in gru_score_map
        has_hist = code in hist_score_map
        if has_gru and has_hist:
            final_scores[code] = (
                LGB_WEIGHT * lgb_s + GRU_WEIGHT * gru_score_map[code] + HIST_WEIGHT * hist_score_map[code]
            )
        elif has_hist:
            w = LGB_WEIGHT + GRU_WEIGHT
            final_scores[code] = w * lgb_s + HIST_WEIGHT * hist_score_map[code]
        elif has_gru:
            final_scores[code] = LGB_WEIGHT * lgb_s + (GRU_WEIGHT + HIST_WEIGHT) * gru_score_map[code]
        else:
            final_scores[code] = lgb_s

    gru_coverage = len([c for c in ts_codes if c in gru_score_map])
    hist_coverage = len([c for c in ts_codes if c in hist_score_map])
    print(f"  Ensemble: LGB×{LGB_WEIGHT} + GRU×{GRU_WEIGHT} + HIST×{HIST_WEIGHT}")
    print(f"  Coverage: GRU={gru_coverage}/{len(ts_codes)}, HIST={hist_coverage}/{len(ts_codes)}")

    # 6. 生成信号（排序，取 top 30）
    signal_list = sorted(final_scores.items(), key=lambda x: x[1], reverse=True)

    top_n = 30
    signals = {
        "date": latest_str,
        "regime": regime,
        "model": f"ensemble_lgb{LGB_WEIGHT}_gru{GRU_WEIGHT}_hist{HIST_WEIGHT}",
        "lgb_weight": LGB_WEIGHT,
        "gru_weight": GRU_WEIGHT,
        "hist_weight": HIST_WEIGHT,
        "gru_coverage": gru_coverage,
        "hist_coverage": hist_coverage,
        "top_signals": [{"ts_code": code, "score": round(float(score), 6)} for code, score in signal_list[:top_n]],
        "all_signals": {code: round(float(score), 6) for code, score in signal_list},
    }

    # 6. 保存
    output_path = os.path.join(SIGNAL_DIR, f"{latest_str}.json")
    with open(output_path, "w") as f:
        json.dump(signals, f, indent=2, ensure_ascii=False)

    print(f"  Top 5: {[(s['ts_code'], s['score']) for s in signals['top_signals'][:5]]}")
    print(f"  Saved: {output_path}")
    print(f"[ml_signal_generate] Done")


if __name__ == "__main__":
    main()
