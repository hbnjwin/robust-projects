"""
services/auto_factor_explorer.py — 轻量版自动因子探索

3步闭环（无需 Docker）：
  1. LLM 生成因子假设（基于历史 IC 反馈）
  2. 本地计算因子 IC（基于 factors_latest.parquet）
  3. IC > threshold 的因子写入 factors_latest.parquet

用法:
    cd /home/tulin/quant
    source .venv/bin/activate
    python services/auto_factor_explorer.py --rounds 5 --ic-threshold 0.05
"""
from __future__ import annotations

import os
import sys
import json
import time
import textwrap
import argparse
import traceback
from pathlib import Path
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from openai import OpenAI

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

# ── 配置 ──────────────────────────────────────────────────────
FACTORS_PATH = _ROOT / "data" / "factors_latest.parquet"
FACTORS_FULL = _ROOT / "data" / "factors_full.parquet"
HISTORY_PATH = _ROOT / "data" / "factor_exploration_history.json"
LOG_PATH     = _ROOT / "logs" / "auto_factor_explorer.log"

LABEL_COL    = os.environ.get("LABEL_COL_OVERRIDE", "label_5d")
SKIP_COLS    = {"ts_code", "trade_date", "label_3d", "label_5d", "label_10d"}
IC_THRESHOLD = 0.05
MAX_ROUNDS   = 5

API_KEY      = os.environ.get("OPENAI_API_KEY", "")
API_BASE     = os.environ.get("OPENAI_API_BASE", "https://unifiedapi.cloud/v1")
CHAT_MODEL   = os.environ.get("CHAT_MODEL", "claude-sonnet-4-6")


# ── 日志 ──────────────────────────────────────────────────────
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
_log_file = open(LOG_PATH, "a", buffering=1)


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    _log_file.write(line + "\n")


# ── LLM ───────────────────────────────────────────────────────
def llm_chat(messages: list, temperature: float = 0.7) -> str:
    client = OpenAI(api_key=API_KEY, base_url=API_BASE)
    resp = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=messages,
        temperature=temperature,
    )
    return resp.choices[0].message.content.strip()


# ── 历史记录 ──────────────────────────────────────────────────
def load_history() -> list:
    if HISTORY_PATH.exists():
        with open(HISTORY_PATH) as f:
            return json.load(f)
    return []


def save_history(history: list):
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_PATH, "w") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


# ── Step 1: LLM 生成因子假设 ──────────────────────────────────
SYSTEM_PROMPT = """你是一名专业的 A 股量化因子研究员，深度了解 A 股市场特性。

【A 股 label_5d 预测的实证规律（基于 2023-2025 全市场数据验证，必须遵守）】
1. 反转效应显著：长期超跌（roc_20/30/60 为负）的股票未来 5 日收益更高，IC 约 -0.06
2. 低波动溢价：近期波动率低（std_5/10/20 小）的股票未来收益更高，IC 约 -0.07
3. 低位反弹：价格处于近期低分位（qtld_20/60 高、min_20/60 高）的股票更可能反弹，IC 约 +0.07
4. K 线实体短：klen 小（实体短，方向不明确）的股票未来收益反而更高，IC 约 -0.07
5. 避免以下无效方向：短期动量延续、量价共振趋势跟随、成交量放大追涨

【有效因子方向（IC 绝对值 > 0.05 的已验证方向）】
- 超跌反转：长期跌幅大 + 近期波动率低 → 未来收益高
- 低位低波：价格在近期低分位 + 波动率收缩 → 反弹概率高
- 多周期超跌共振：20日/30日/60日 ROC 均为负且绝对值大 → 反转信号强
- 波动率压缩：std 多周期同步收缩 → 蓄势待发
- 价格低位 + 成交量萎缩：qtld 高 + vstd 低 → 底部特征

现有因子列（均为数值型）：
{feature_list}

规则：
1. 新因子必须基于现有列的数学组合
2. 代码接收 DataFrame df，返回 pd.Series（index 与 df 相同）
3. 因子名用英文小写+下划线
4. 不要使用外部数据源，只用 df 中已有的列
5. 代码中不能有 import 语句，可直接使用 pd 和 np
6. 优先生成反转类、低波溢价类、超跌低位类因子
7. 因子方向：因子值越大 → 预期未来收益越高
"""

HYPOTHESIS_PROMPT = """历史探索记录（最近 {n} 轮）：
{history_summary}

已知有效单因子（供参考，不要重复）：
- std_10 IC=-0.074（低波动率预测高收益，因子需取负）
- qtld_60 IC=+0.072（60日低分位数高 → 未来收益高）
- roc_30 IC=-0.062（长期跌幅大 → 未来反转，因子需取负）
- min_60 IC=+0.068（60日最低价高 → 价格相对低位）

请提出一个新的组合因子假设，要求：
- 与历史因子不重复
- 基于反转/低波/超跌方向的组合，IC 绝对值预期 > 0.05
- 组合逻辑：将多个有效单因子非线性组合，放大信号

请严格按以下 JSON 格式返回（不要有其他内容，不要 markdown 代码块）：
{{
  "factor_name": "因子英文名",
  "hypothesis": "因子假设（一句话）",
  "logic": "经济学逻辑（2-3句）",
  "code": "def compute_factor(df):\\n    # 低波动 + 超跌组合\\n    low_vol = -df['std_10']\\n    oversold = -df['roc_30']\\n    result = low_vol * oversold\\n    return result"
}}
"""


def generate_hypothesis(history: list, feature_list: list) -> Optional[dict]:
    n = min(len(history), 10)
    if n == 0:
        history_summary = "暂无历史记录，这是第一轮探索。"
    else:
        lines = []
        for h in history[-n:]:
            ic_str = f"IC={h['ic']:.4f}" if h.get("ic") is not None else "IC=N/A"
            status = "已加入" if h.get("accepted") else "未通过"
            lines.append(f"- {h['factor_name']}: {h.get('hypothesis', '')} | {ic_str} | {status}")
        history_summary = "\n".join(lines)

    system = SYSTEM_PROMPT.format(feature_list=", ".join(feature_list))
    user = HYPOTHESIS_PROMPT.format(n=n, history_summary=history_summary)

    try:
        response = llm_chat([
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ])
        start = response.find("{")
        end = response.rfind("}") + 1
        if start == -1 or end == 0:
            log("[LLM] 返回格式错误，无法解析 JSON")
            return None
        raw = response[start:end]
        # code 字段里的换行符需要先转义才能被 json.loads 接受
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            # 尝试用 ast.literal_eval 或手动修复换行
            import re
            # 把 "code": "..." 里的裸换行替换成 \n
            fixed = re.sub(
                r'("code"\s*:\s*")(.*?)("(?:\s*[,}]))',
                lambda m: m.group(1) + m.group(2).replace('\n', '\\n').replace('\t', '\\t') + m.group(3),
                raw,
                flags=re.DOTALL,
            )
            result = json.loads(fixed)
        log(f"[LLM] 生成假设: {result['factor_name']} — {result.get('hypothesis', '')}")
        return result
    except Exception as e:
        log(f"[LLM] 生成失败: {e}")
        return None


# ── Step 2: 本地计算因子 IC ───────────────────────────────────
def compute_factor_ic(
    hypothesis: dict,
    df: pd.DataFrame,
    label_col: str = LABEL_COL,
) -> tuple:
    code = hypothesis.get("code", "")
    factor_name = hypothesis.get("factor_name", "unknown")

    local_ns = {"pd": pd, "np": np, "df": df.copy()}
    try:
        exec(textwrap.dedent(code), local_ns)
        compute_fn = local_ns.get("compute_factor")
        if compute_fn is None:
            log(f"[IC] 代码中未找到 compute_factor 函数")
            return float("nan"), None

        factor_series = compute_fn(df)

        if not isinstance(factor_series, pd.Series):
            log(f"[IC] compute_factor 返回类型错误: {type(factor_series)}")
            return float("nan"), None

        # 按日期截面计算 Spearman IC
        df_eval = df[["trade_date", label_col]].copy()
        df_eval["factor"] = factor_series.values

        daily_ics = []
        for date, grp in df_eval.groupby("trade_date"):
            valid = grp.dropna()
            if len(valid) < 20:
                continue
            ic, _ = spearmanr(valid["factor"], valid[label_col])
            if not np.isnan(ic):
                daily_ics.append(ic)

        if not daily_ics:
            log(f"[IC] {factor_name}: 无有效截面数据")
            return float("nan"), None

        mean_ic = float(np.mean(daily_ics))
        icir = mean_ic / (np.std(daily_ics) + 1e-8)
        log(f"[IC] {factor_name}: mean_IC={mean_ic:.4f}, ICIR={icir:.4f}, 截面数={len(daily_ics)}")
        return mean_ic, factor_series

    except Exception as e:
        log(f"[IC] {factor_name} 执行失败: {e}\n{traceback.format_exc()}")
        return float("nan"), None


# ── Step 3: 写入因子库 ────────────────────────────────────────
def add_factor_to_parquet(
    factor_name: str,
    factor_series: pd.Series,
    df_eval: pd.DataFrame,
    parquet_path: Path,
):
    """将新因子写入 factors_latest.parquet（对齐 index）"""
    df_target = pd.read_parquet(parquet_path)
    if factor_name in df_target.columns:
        log(f"[写入] {factor_name} 已存在，跳过")
        return

    # df_eval 是截断数据（eval_start 之后），df_target 是 factors_latest（近4个月）
    # 用 ts_code + trade_date 做 key 对齐
    df_target["trade_date"] = pd.to_datetime(df_target["trade_date"])
    df_eval_copy = df_eval[["ts_code", "trade_date"]].copy()
    df_eval_copy[factor_name] = factor_series.values

    df_target = df_target.merge(
        df_eval_copy[["ts_code", "trade_date", factor_name]],
        on=["ts_code", "trade_date"],
        how="left",
    )
    df_target.to_parquet(parquet_path, index=False)
    filled = df_target[factor_name].notna().sum()
    log(f"[写入] {factor_name} 已加入 {parquet_path.name}，填充 {filled}/{len(df_target)} 行，列数: {len(df_target.columns)}")


# ── 主循环 ────────────────────────────────────────────────────
def run_exploration(
    n_rounds: int = MAX_ROUNDS,
    ic_threshold: float = IC_THRESHOLD,
    use_full: bool = False,
    eval_start: str = "2023-01-01",
):
    log(f"=== auto_factor_explorer 启动 | rounds={n_rounds} ic_threshold={ic_threshold} eval_start={eval_start} ===")

    data_path = FACTORS_FULL if use_full else FACTORS_PATH
    log(f"加载因子数据: {data_path}")
    df_all = pd.read_parquet(data_path)
    df_all["trade_date"] = pd.to_datetime(df_all["trade_date"])

    # IC 计算用截断数据，节省内存和时间
    df = df_all[df_all["trade_date"] >= pd.Timestamp(eval_start)].copy()
    log(f"全量数据: {df_all.shape}，IC评估范围: {eval_start} ~ {df['trade_date'].max().date()}，行数: {len(df)}")
    del df_all  # 释放全量数据内存

    feature_cols = [c for c in df.columns if c not in SKIP_COLS]
    log(f"特征数: {len(feature_cols)}, 截面数: {df['trade_date'].nunique()}")

    history = load_history()
    accepted_count = 0

    for round_i in range(1, n_rounds + 1):
        log(f"\n{'='*50}")
        log(f"Round {round_i}/{n_rounds}")
        log(f"{'='*50}")

        hypothesis = generate_hypothesis(history, feature_cols)
        if hypothesis is None:
            log(f"[Round {round_i}] 假设生成失败，跳过")
            continue

        factor_name = hypothesis["factor_name"]

        existing_names = {h["factor_name"] for h in history}
        if factor_name in existing_names or factor_name in df.columns:
            log(f"[Round {round_i}] {factor_name} 已存在，跳过")
            history.append({
                **hypothesis,
                "ic": None, "accepted": False,
                "reason": "duplicate",
                "timestamp": datetime.now().isoformat(),
            })
            save_history(history)
            continue

        ic, factor_series = compute_factor_ic(hypothesis, df)

        accepted = (not np.isnan(ic)) and (ic >= ic_threshold)
        if accepted:
            reason = f"IC={ic:.4f} >= {ic_threshold}"
        elif np.isnan(ic):
            reason = "执行失败"
        else:
            reason = f"IC={ic:.4f} < {ic_threshold}"

        record = {
            **hypothesis,
            "ic": ic if not np.isnan(ic) else None,
            "accepted": accepted,
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
        }

        if accepted and factor_series is not None:
            add_factor_to_parquet(factor_name, factor_series, df, FACTORS_PATH)
            df[factor_name] = factor_series.values
            feature_cols.append(factor_name)
            accepted_count += 1
            log(f"✅ {factor_name} 已加入因子库 (IC={ic:.4f})")
        else:
            log(f"❌ {factor_name} 未通过 ({reason})")

        history.append(record)
        save_history(history)

        if round_i < n_rounds:
            time.sleep(2)

    log(f"\n=== 探索完成 | 共 {n_rounds} 轮，新增因子 {accepted_count} 个 ===")

    print("\n本次探索结果：")
    for h in history[-n_rounds:]:
        ic_str = f"IC={h['ic']:.4f}" if h.get("ic") is not None else "IC=N/A"
        status = "✅" if h.get("accepted") else "❌"
        print(f"  {status} {h['factor_name']}: {h.get('hypothesis', '')} | {ic_str}")

    return accepted_count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="自动因子探索")
    parser.add_argument("--rounds", type=int, default=MAX_ROUNDS)
    parser.add_argument("--ic-threshold", type=float, default=IC_THRESHOLD)
    parser.add_argument("--full", action="store_true", help="使用 factors_full.parquet")
    parser.add_argument("--eval-start", type=str, default="2023-01-01", help="IC 计算起始日期")
    args = parser.parse_args()

    # 加载 .env
    env_path = _ROOT / "RD-Agent" / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"'))

    run_exploration(
        n_rounds=args.rounds,
        ic_threshold=args.ic_threshold,
        use_full=args.full,
        eval_start=args.eval_start,
    )
