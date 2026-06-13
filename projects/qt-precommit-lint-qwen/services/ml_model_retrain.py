"""
月度模型重训练
全量因子计算 → 数据集切分 → 训练 → 评估 → 保存
自动对比新旧模型 IC，只有新模型更好才替换

调度: 每月1日 23:00
"""

import sys
import os
import json
import time
import shutil
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from factor_engine.pipeline import FactorPipeline
from ml.dataset import FactorDataset
from ml.trainer import RegimeAwareTrainer, generate_regime_labels
from ml.evaluator import calc_daily_ic, ic_summary


MODEL_DIR = "ml/model_store"
FACTORS_PATH = "data/factors_full.parquet"
REGIME_PATH = "data/regime_labels.parquet"


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    version = datetime.now().strftime("v%Y%m%d")
    print(f"[ml_model_retrain] {today}, version: {version}")

    # 1. 全量因子计算
    print("\n[Step 1] Full factor computation...")
    t0 = time.time()
    pipe = FactorPipeline()
    pipe.run(
        start_date="2018-01-01",
        end_date=today,
        norm_method="robust_zscore",
        output_path=FACTORS_PATH,
    )
    pipe.close()
    print(f"  Done in {time.time() - t0:.1f}s")

    # 2. 生成 Regime 标签
    print("\n[Step 2] Generate regime labels...")
    t1 = time.time()
    regime_df = generate_regime_labels("2018-01-01", today)
    regime_df.to_parquet(REGIME_PATH)
    print(f"  Done in {time.time() - t1:.1f}s")

    # 3. 构建数据集（滚动窗口：最近5年训练，最近1年验证，最近3月测试）
    print("\n[Step 3] Build dataset...")
    now = datetime.now()
    test_start = (now.replace(day=1) - pd.DateOffset(months=3)).strftime("%Y-%m-%d")
    valid_start = (now.replace(day=1) - pd.DateOffset(months=15)).strftime("%Y-%m-%d")
    valid_end = (now.replace(day=1) - pd.DateOffset(months=3) - pd.DateOffset(days=1)).strftime("%Y-%m-%d")
    train_end = (now.replace(day=1) - pd.DateOffset(months=15) - pd.DateOffset(days=1)).strftime("%Y-%m-%d")

    ds = FactorDataset(
        FACTORS_PATH,
        train_period=("2018-01-01", train_end),
        valid_period=(valid_start, valid_end),
        test_period=(test_start, today),
        label_col="label_3d",
    )

    # 4. 训练新模型
    print("\n[Step 4] Train new models...")
    t2 = time.time()
    trainer = RegimeAwareTrainer(
        dataset=ds,
        regime_labels=regime_df,
        model_type="lgb",
        model_kwargs={
            "learning_rate": 0.05,
            "num_leaves": 63,
            "num_boost_round": 2000,
            "early_stopping_rounds": 100,
            "verbose": 200,
        },
    )
    trainer.train_all(min_samples=5000)
    print(f"  Training done in {time.time() - t2:.1f}s")

    # 5. 评估新模型
    print("\n[Step 5] Evaluate new model...")
    new_ic_df = calc_daily_ic(ds, trainer.global_model, segment="test")
    new_summary = ic_summary(new_ic_df)
    print(f"  New model IC: {new_summary}")

    # 6. 对比旧模型
    old_model_dir = os.path.join(MODEL_DIR, "v1")
    should_replace = True

    if os.path.exists(os.path.join(old_model_dir, "global.pkl")):
        from ml.models import BaseModel

        old_model = BaseModel.load(os.path.join(old_model_dir, "global.pkl"))
        old_ic_df = calc_daily_ic(ds, old_model, segment="test")
        old_summary = ic_summary(old_ic_df)
        print(f"  Old model IC: {old_summary}")

        if new_summary["ic_mean"] <= old_summary["ic_mean"]:
            print(f"  [WARN] New model IC ({new_summary['ic_mean']}) <= Old ({old_summary['ic_mean']})")
            print(f"  Keeping old model, saving new as {version} for reference")
            should_replace = False

    # 7. 保存
    new_dir = os.path.join(MODEL_DIR, version)
    trainer.save_all(new_dir)

    if should_replace:
        # 备份旧 v1
        if os.path.exists(old_model_dir):
            backup_dir = os.path.join(MODEL_DIR, "v1_backup")
            if os.path.exists(backup_dir):
                shutil.rmtree(backup_dir)
            shutil.copytree(old_model_dir, backup_dir)
            print(f"  Old model backed up to {backup_dir}")

        # 复制新模型到 v1（生产目录）
        if os.path.exists(old_model_dir):
            shutil.rmtree(old_model_dir)
        shutil.copytree(new_dir, old_model_dir)
        print(f"  New model deployed to {old_model_dir}")

    # 8. 重新生成 ML 信号
    print("\n[Step 8] Regenerate ML signals...")
    t3 = time.time()
    from signals.signal_generator import MLSignalGenerator

    gen = MLSignalGenerator(
        model_dir=old_model_dir if should_replace else new_dir,
        factors_path=FACTORS_PATH,
        regime_path=REGIME_PATH,
    )
    all_signals = gen.get_all_signals()

    records = []
    for date_str, signals in all_signals.items():
        for ts_code, score in signals.items():
            records.append({"trade_date": date_str, "ts_code": ts_code, "score": score})
    pd.DataFrame(records).to_parquet("data/ml_signals.parquet", compression="zstd")
    print(f"  Signals regenerated: {len(all_signals)} days ({time.time() - t3:.1f}s)")

    print(f"\n[ml_model_retrain] Done. Version: {version}, deployed: {should_replace}")


if __name__ == "__main__":
    main()
