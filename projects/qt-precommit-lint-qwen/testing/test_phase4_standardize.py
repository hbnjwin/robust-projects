"""
Phase 4 标准化模块验证脚本
验证：
1. 单 Alpha 无标准化 → 等价透传
2. Rank 标准化逻辑正确
3. Z-score 标准化逻辑正确
4. 多 Alpha 融合权重归一化正确
"""

import sys

sys.path.insert(0, "/home/tulin/quant")

from alpha.alpha_manager import AlphaManager
from alpha.adapters.factor_alpha import FactorAlpha

# ── 测试数据 ──────────────────────────────────────────────────
test_scores = {"A": 1.0, "B": 3.0, "C": 2.0, "D": 0.5}
date = "2023-01-05"

# ── Test 1: 单 Alpha 无标准化 → 等价透传 ─────────────────────
alpha = FactorAlpha({date: test_scores})
manager = AlphaManager(standardize=None)
manager.register(alpha, weight=1.0)
result = manager.generate(date)
assert result == test_scores, f"Test 1 FAIL: {result}"
print("✅ Test 1 PASS: 单 Alpha 无标准化等价透传")

# ── Test 2: Rank 标准化 ───────────────────────────────────────
alpha2 = FactorAlpha({date: test_scores})
manager2 = AlphaManager(standardize="rank")
manager2.register(alpha2, weight=1.0)
result2 = manager2.generate(date)
# 排序: D(0.5) < A(1.0) < C(2.0) < B(3.0)
# rank: D=0/3, A=1/3, C=2/3, B=3/3
expected_rank = {"D": 0.0, "A": 1 / 3, "C": 2 / 3, "B": 1.0}
for k, v in expected_rank.items():
    assert abs(result2[k] - v) < 1e-9, f"Test 2 FAIL: {k}={result2[k]} expected {v}"
print(f"✅ Test 2 PASS: Rank 标准化正确 {result2}")

# ── Test 3: Z-score 标准化 ────────────────────────────────────
import numpy as np

alpha3 = FactorAlpha({date: test_scores})
manager3 = AlphaManager(standardize="zscore")
manager3.register(alpha3, weight=1.0)
result3 = manager3.generate(date)
vals = list(test_scores.values())
mean, std = np.mean(vals), np.std(vals)
for k, v in test_scores.items():
    expected = (v - mean) / std
    assert abs(result3[k] - expected) < 1e-9, f"Test 3 FAIL: {k}"
print(f"✅ Test 3 PASS: Z-score 标准化正确")

# ── Test 4: 多 Alpha 权重归一化 ───────────────────────────────
scores_a = {"X": 1.0, "Y": 2.0}
scores_b = {"X": 3.0, "Y": 4.0}
alpha_a = FactorAlpha({date: scores_a})
alpha_b = FactorAlpha({date: scores_b})
manager4 = AlphaManager(standardize=None)
manager4.register(alpha_a, weight=1.0)
manager4.register(alpha_b, weight=1.0)
result4 = manager4.generate(date)
# 权重各 0.5，X = 0.5*1 + 0.5*3 = 2.0, Y = 0.5*2 + 0.5*4 = 3.0
assert abs(result4["X"] - 2.0) < 1e-9, f"Test 4 FAIL X: {result4['X']}"
assert abs(result4["Y"] - 3.0) < 1e-9, f"Test 4 FAIL Y: {result4['Y']}"
print(f"✅ Test 4 PASS: 多 Alpha 权重融合正确 {result4}")

print("\n🎉 所有测试通过，Phase 4 标准化模块验证完成")
