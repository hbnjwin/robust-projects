# .vulture_whitelist.py
# Vulture 误报白名单 — 本文件中的符号不会被 vulture 标记为死代码
# 生成时间: 2026-06-13
#
# 误报类型说明:
#   [PyTorch] nn.Module.forward() 通过 __call__ 隐式调用，vulture 无法识别
#   [pytest]  test_* 函数/类被 pytest 动态发现，vulture 无法识别
#   [ABC]     抽象方法/接口方法被子类覆写或框架回调，vulture 无法识别
#   [Config]  配置常量被外部脚本/文档引用，vulture 无法识别

# ============================================================
# PyTorch nn.Module.forward() — 通过 model(x) 隐式调用
# ============================================================
# gpu-train/
GRUModel.forward  # gpu-train/train_gru.py, train_gru_gpu.py
GATModel.forward  # gpu-train/train_gats.py, train_gats_gpu.py
HISTModel.forward  # gpu-train/train_hist.py, train_hist_gpu.py
GraphAttentionBlock.forward  # gpu-train/train_gats_gpu.py

# services/
_GRUModel.forward  # services/gru_signal_generate.py, services/walk_forward.py, services/backtest_oos.py
HISTModel.forward  # services/hist_signal_generate.py

# testing/
_GRU.forward  # testing/hist_backtest_compare.py
_HIST.forward  # testing/hist_backtest_compare.py

# qlib_bridge/
GRUModel.forward  # qlib_bridge/train_gru.py

# ============================================================
# pytest 测试函数 — 由 pytest runner 动态发现
# vulture 不会标记 test_ 前缀函数，此处仅作记录
# ============================================================
# testing/test_phase1.py ~ test_phase5.py
# testing/test_architecture.py
# testing/test_factor.py
# testing/test_p0_sql_injection.py
# testing/test_p0_t1_lotsize.py
# testing/test_p1_fixes.py

# ============================================================
# ABC / 框架回调 — 被 VnPy 框架或事件系统调用
# ============================================================
on_order  # core/gateway.py, live/live_engine.py — VnPy gateway callback
on_order  # live/live_engine.py
query_position  # vnpy_ext/pg_daily_gateway.py, tx_realtime_gateway.py — VnPy gateway interface
query_history  # vnpy_ext/pg_daily_gateway.py, tx_realtime_gateway.py — VnPy gateway interface

# ============================================================
# 配置 / 常量 — 被外部脚本或文档引用
# ============================================================
CREDIT_BUY  # quant-qmt-ptrade/.../xtconstant.py — XtQuant SDK 常量定义
CREDIT_SELL  # 同上
ORDER_UNREPORTED  # 同上
ORDER_REPORTED  # 同上
