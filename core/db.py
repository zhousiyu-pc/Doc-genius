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
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            password_salt TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

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

        -- 对话会话表：存储 LLM 多轮对话的会话状态
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id TEXT PRIMARY KEY,
            title TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            outline TEXT DEFAULT '',
            task_id TEXT DEFAULT '',
            user_id TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        -- 对话消息表：存储每轮对话的消息内容
        CREATE TABLE IF NOT EXISTS chat_messages (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            msg_type TEXT DEFAULT 'text',
            metadata TEXT DEFAULT '{}',
            created_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
        );

        CREATE INDEX IF NOT EXISTS idx_chat_messages_session
            ON chat_messages(session_id);
    """)

    # 兼容旧库：给 chat_sessions 表添加缺失的列
    for alter_sql in [
        "ALTER TABLE chat_sessions ADD COLUMN mode TEXT DEFAULT 'free'",
        "ALTER TABLE chat_sessions ADD COLUMN current_stage TEXT DEFAULT 'discovery'",
        "ALTER TABLE chat_sessions ADD COLUMN user_id TEXT DEFAULT ''",
    ]:
        try:
            conn.execute(alter_sql)
        except sqlite3.OperationalError:
            pass

    # 在 user_id 列确保存在后再建索引
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON chat_sessions(user_id)")
    except sqlite3.OperationalError:
        pass

    # 分享链接表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS share_links (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            user_id TEXT DEFAULT '',
            token TEXT UNIQUE NOT NULL,
            expires_at TEXT,
            password TEXT DEFAULT '',
            view_count INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_share_links_token ON share_links(token)")

    # 模板表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS templates (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            category TEXT DEFAULT '',
            icon TEXT DEFAULT '',
            prompt TEXT NOT NULL,
            mode TEXT DEFAULT 'free',
            is_builtin INTEGER DEFAULT 0,
            use_count INTEGER DEFAULT 0,
            created_by TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # 版本历史表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS session_versions (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            version_num INTEGER NOT NULL,
            title TEXT DEFAULT '',
            outline TEXT DEFAULT '',
            snapshot TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_session_versions_sid ON session_versions(session_id)")

    # 套餐配置表（内置套餐 + 用户自定义）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS plans (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            display_name TEXT NOT NULL,
            price_monthly INTEGER DEFAULT 0,
            price_quarterly INTEGER DEFAULT 0,
            price_yearly INTEGER DEFAULT 0,
            daily_chat_limit INTEGER DEFAULT 10,
            monthly_doc_limit INTEGER DEFAULT 3,
            max_file_size_mb INTEGER DEFAULT 5,
            max_versions INTEGER DEFAULT 0,
            allowed_models TEXT DEFAULT '',
            features TEXT DEFAULT '',
            sort_order INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL
        )
    """)

    # 用户订阅表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            plan_id TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            billing_cycle TEXT DEFAULT 'monthly',
            started_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            auto_renew INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (plan_id) REFERENCES plans(id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions(user_id)")

    # 用量记录表（每日统计）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usage_records (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            record_date TEXT NOT NULL,
            chat_count INTEGER DEFAULT 0,
            doc_count INTEGER DEFAULT 0,
            upload_count INTEGER DEFAULT 0,
            UNIQUE(user_id, record_date)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_user_date ON usage_records(user_id, record_date)")

    conn.commit()
    conn.close()
    logger.info("数据库初始化完成: %s", DB_PATH)
