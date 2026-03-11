"""
数据库管理模块
=============
SQLite 数据库的初始化、连接管理和线程安全封装。
"""

import sqlite3
import threading
import logging
from contextlib import contextmanager

from .config import DB_PATH

logger = logging.getLogger("agent_skills.db")
_local = threading.local()


@contextmanager
def get_db():
    """
    获取线程安全的 SQLite 连接。
    每个线程使用独立的连接，避免多线程竞争。
    """
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(DB_PATH, timeout=30)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA busy_timeout=10000")
    try:
        yield _local.conn
        _local.conn.commit()
    except Exception:
        _local.conn.rollback()
        raise


def init_db():
    """初始化数据库表结构"""
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            feature_list TEXT NOT NULL,
            context TEXT NOT NULL,
            business_model TEXT DEFAULT '',
            target_market TEXT DEFAULT '',
            platforms TEXT DEFAULT '',
            detail_level TEXT DEFAULT '详细',
            status TEXT DEFAULT 'pending',
            total_count INTEGER DEFAULT 0,
            completed_count INTEGER DEFAULT 0,
            failed_count INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            finished_at TEXT
        );

        CREATE TABLE IF NOT EXISTS sub_tasks (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            feature_name TEXT NOT NULL,
            seq_index INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            result TEXT,
            retry_count INTEGER DEFAULT 0,
            error_message TEXT,
            started_at TEXT,
            finished_at TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        );

        CREATE INDEX IF NOT EXISTS idx_sub_tasks_task_id ON sub_tasks(task_id);
        CREATE INDEX IF NOT EXISTS idx_sub_tasks_status ON sub_tasks(status);
    """)

    # 兼容旧库：给 tasks 表添加 result_file 列（如已存在则忽略）
    try:
        conn.execute("ALTER TABLE tasks ADD COLUMN result_file TEXT")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()
    logger.info("数据库初始化完成: %s", DB_PATH)
