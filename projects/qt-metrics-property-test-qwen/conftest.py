"""pytest 配置：hypothesis profile 注册

用法:
  pytest --hypothesis-profile=ci        # CI 快速回归（200 用例）
  pytest --hypothesis-profile=thorough  # 本地深度探索（1000 用例）

也可通过环境变量 HYPOTHESIS_PROFILE 控制。
"""
from hypothesis import settings

# ── hypothesis profile 定义 ─────────────────────────────────────────
# ci:       快速回归，适合 CI pipeline，保证 30 秒内完成
settings.register_profile("ci", max_examples=200, deadline=5000)
# thorough: 深度探索，适合本地调试
settings.register_profile("thorough", max_examples=1000, deadline=10000)

# 默认加载 ci profile；可通过 HYPOTHESIS_PROFILE 环境变量覆盖
import os
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "ci"))
