"""
统一日志框架 - P2-15
支持文件 + 控制台输出，所有模块共用。
"""

import os
import logging

LOG_DIR = os.path.expanduser("~/quant/logs")
os.makedirs(LOG_DIR, exist_ok=True)

_FMT = "%(asctime)s [%(name)s] %(levelname)s %(message)s"
_formatter = logging.Formatter(_FMT)

# 文件 handler（全局共享）
_file_handler = logging.FileHandler(os.path.join(LOG_DIR, "quant.log"))
_file_handler.setFormatter(_formatter)

# 控制台 handler
_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_formatter)


def get_logger(name: str, level=logging.INFO) -> logging.Logger:
    """获取统一配置的 logger"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(level)
        logger.addHandler(_file_handler)
        logger.addHandler(_console_handler)
    return logger
