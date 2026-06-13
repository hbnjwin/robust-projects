"""
llm_factor_gen.py - LLM 因子生成器（本地 venv 版，无需 Docker）
基于 factors_latest.parquet 的已有特征列，用 LLM 生成组合因子
"""

import os, sys, json, traceback, subprocess, tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np
from openai import OpenAI

# ── 配置 ──────────────────────────────────────────────────────────────
PYTHON_BIN = "/home/tulin/quant/.venv/bin/python"
DATA_PATH = "/home/tulin/quant/data/factors_latest.parquet"
OUTPUT_DIR = Path("/home/tulin/quant/data/llm_factors")
IC_THRESHOLD = 0.03
N_FACTORS = 5

API_KEY = os.environ.get("OPENAI_API_KEY", "")
API_BASE = os.environ.get("OPENAI_API_BASE", "https://unifiedapi.cloud/v1")
CHAT_MODEL = os.environ.get("CHAT_MODEL", "claude-sonnet-4-6")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Prompt ────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """你是A股量化因子研究专家。基于已有特征列生成新的组合因子。

可用特征列（均已标准化）：
roc_5/10/20/30/60, ma_5/10/20/30/60, std_5/10/20/30/60,
beta_5/10/20/30/60, rsqr_5/10/20/30/60, rsv_5/20/60,
vol_ratio, vma_5/20, vstd_5/20/60,
cntp_5/10/20, cntd_5/10/20, sump_5/20, sumn_5/20, sumd_5/20,
corr_ret_vol_10/20, kmid, klen, kup, klow, ksft,
max_20/60, min_20/60, qtlu_20/60, qtld_20/60

禁止使用: label_3d, label_5d, label_10d

函数签名必须是：
def compute_factor(df: pd.DataFrame) -> pd.Series:
    ...
    return result

只用 pandas/numpy，处理 NaN，只返回函数代码，不要任何解释。"""

FACTOR_IDEAS = [
    "动量质量因子：roc_5与roc_20的比值，捕捉短期动量相对中期的强度",
    "趋势确定性因子：beta_20乘以rsqr_20，只有趋势明确时才给高分",
    "量价背离因子：corr_ret_vol_20取反，量价负相关时可能反转",
    "波动率调整动量：roc_20除以(std_20+1e-6)，风险调整后的动量",
    "超买超卖因子：rsv_5与rsv_20的差值，短期相对中期的超买超卖",
    "成交量异动：vol_ratio乘以vma_5与vma_20的比值",
    "反转信号：sumn_5减去sump_5，近期下跌累计超过上涨时看多",
    "趋势动量综合：beta_5乘以roc_5，方向和强度双重确认",
]


def generate_factor_code(idea: str) -> str:
    client = OpenAI(api_key=API_KEY, base_url=API_BASE)
    resp = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"请根据以下思路生成因子函数：\n{idea}"},
        ],
        temperature=0.3,
        max_tokens=600,
    )
    code = resp.choices[0].message.content.strip()
    if "```python" in code:
        code = code.split("```python")[1].split("```")[0].strip()
    elif "```" in code:
        code = code.split("```")[1].split("```")[0].strip()
    return code


def run_factor_code(code: str, df: pd.DataFrame):
    script_content = f"""import pandas as pd
import numpy as np
import sys

{code}

df = pd.read_parquet(sys.argv[1])
result = compute_factor(df)
result = result.fillna(0)
result.to_json(sys.argv[2])
"""
    tmp_script = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False)
    tmp_script.write(script_content)
    tmp_script.close()

    tmp_out = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp_out.close()

    tmp_data = tempfile.NamedTemporaryFile(suffix=".parquet", delete=False)
    tmp_data.close()
    df.to_parquet(tmp_data.name)

    try:
        r = subprocess.run(
            [PYTHON_BIN, tmp_script.name, tmp_data.name, tmp_out.name], capture_output=True, text=True, timeout=60
        )
        if r.returncode != 0:
            print(f"  执行错误: {r.stderr[-400:]}")
            return None
        return pd.read_json(tmp_out.name, typ="series")
    except subprocess.TimeoutExpired:
        print("  执行超时")
        return None
    except Exception as e:
        print(f"  异常: {e}")
        return None
    finally:
        for p in [tmp_script.name, tmp_out.name, tmp_data.name]:
            try:
                os.unlink(p)
            except Exception:
                pass


def compute_ic(factor: pd.Series, df: pd.DataFrame, label_col: str = "label_5d") -> float:
    label = df[label_col]
    aligned = pd.concat([factor, label], axis=1).dropna()
    if len(aligned) < 100:
        return 0.0
    ic = aligned.iloc[:, 0].rank().corr(aligned.iloc[:, 1].rank(), method="spearman")
    return float(ic) if not np.isnan(ic) else 0.0


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"[{ts}] LLM 因子生成开始，目标 {N_FACTORS} 个")
    print(f"模型: {CHAT_MODEL} | 数据: {DATA_PATH}")
    print("-" * 60)

    df = pd.read_parquet(DATA_PATH)
    print(f"数据: {df.shape[0]} 行 x {df.shape[1]} 列")

    results = []
    for i, idea in enumerate(FACTOR_IDEAS[:N_FACTORS]):
        print(f"\n[{i + 1}/{N_FACTORS}] ..")
        try:
            code = generate_factor_code(idea)
            print(f"  代码生成 ({len(code)} chars)")

            factor = run_factor_code(code, df)
            if factor is None:
                results.append({"idea": idea, "ic": 0.0, "abs_ic": 0.0, "kept": False, "code": code})
                continue

            ic = compute_ic(factor, df)
            abs_ic = abs(ic)
            kept = abs_ic >= IC_THRESHOLD
            print(f"  Rank IC(5d) = {ic:+.4f}  {'✅ 保留' if kept else '⚠️ IC 不足'}")

            results.append({"idea": idea, "ic": ic, "abs_ic": abs_ic, "kept": kept, "code": code})

            if kept:
                name = f"llm_factor_{i + 1:02d}_{ts}"
                factor.to_parquet(OUTPUT_DIR / f"{name}.parquet")
                with open(OUTPUT_DIR / f"{name}.py", "w") as fw:
                    fw.write(f"# 思路: {idea}\n# IC={ic:.4f}\n\n{code}\n")
                print(f"  已保存: {name}")

        except Exception as e:
            print(f"  ❌ 异常: {e}")
            traceback.print_exc()
            results.append({"idea": idea, "ic": 0.0, "abs_ic": 0.0, "kept": False, "error": str(e)})

    print("\n" + "=" * 60)
    kept_list = [r for r in results if r["kept"]]
    print(f"结果: {len(results)} 个因子，通过阈值(IC>{IC_THRESHOLD}): {len(kept_list)} 个\n")
    for r in sorted(results, key=lambda x: x["abs_ic"], reverse=True):
        mark = "✅" if r["kept"] else "❌"
        print(f"  {mark} IC={r['ic']:+.4f}  {r['idea'][:55]}")

    summary_path = OUTPUT_DIR / f"summary_{ts}.json"
    with open(summary_path, "w", encoding="utf-8") as fw:
        json.dump(results, fw, ensure_ascii=False, indent=2, default=str)
    print(f"\n汇总: {summary_path}")
    return len(kept_list)


if __name__ == "__main__":
    sys.exit(0 if main() >= 0 else 1)
