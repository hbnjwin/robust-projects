"""
DuckDB 因子计算引擎
从 PostgreSQL 读取行情数据，在 DuckDB 内完成因子计算、截面标准化、标签生成。
"""

from .pipeline import FactorPipeline

__all__ = ["FactorPipeline"]
