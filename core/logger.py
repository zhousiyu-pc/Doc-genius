"""
日志管理模块
==========
提供全局日志配置和按任务隔离的日志记录器。
日志文件按时间命名，便于按日期查找和清理。
"""

import os
import datetime
import logging

from .config import LOG_DIR

_LOG_FMT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"


def setup_logging():
    """配置全局日志格式"""
    logging.basicConfig(
        level=logging.INFO,
        format=_LOG_FMT,
        datefmt=_DATE_FMT,
    )


def get_task_logger(task_id: str) -> logging.Logger:
    """
    为每个任务创建独立的文件日志记录器。
    文件名格式：task_YYYYMMDD_HHMMSS_{task_id}.log
    """
    task_logger = logging.getLogger(f"task.{task_id}")
    if not task_logger.handlers:
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = os.path.join(LOG_DIR, f"task_{now}_{task_id}.log")
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(logging.Formatter(_LOG_FMT, datefmt=_DATE_FMT))
        task_logger.addHandler(handler)
        task_logger.setLevel(logging.DEBUG)
    return task_logger
