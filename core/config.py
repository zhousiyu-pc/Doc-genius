"""
全局配置模块
==========
统一管理所有环境变量和配置项。
支持通过环境变量覆盖默认值。
提供配置验证和类型安全。
"""

import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass(frozen=True)
class ServerConfig:
    """服务器配置"""
    host: str = "0.0.0.0"
    port: int = 8766
    debug: bool = False


@dataclass(frozen=True)
class LLMConfig:
    """LLM 配置"""
    api_key: str
    model: str = "qwen-plus"
    api_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    timeout: int = 180
    temperature: float = 0.3
    max_retries: int = 6
    retry_intervals: tuple = (15, 30, 45, 60, 90, 120)


@dataclass(frozen=True)
class TaskConfig:
    """任务管理配置"""
    workers: int = 3
    max_retries: int = 3
    retry_intervals: tuple = (15, 30, 60)


@dataclass(frozen=True)
class StorageConfig:
    """存储配置"""
    data_dir: str
    log_dir: str
    db_path: str
    default_save_dir: str


class Config:
    """统一配置管理器"""
    
    _server: Optional[ServerConfig] = None
    _llm: Optional[LLMConfig] = None
    _task: Optional[TaskConfig] = None
    _storage: Optional[StorageConfig] = None
    
    @classmethod
    def _get_int(cls, key: str, default: int) -> int:
        """安全获取整数配置"""
        try:
            return int(os.environ.get(key, str(default)))
        except (ValueError, TypeError):
            return default
    
    @classmethod
    def _get_float(cls, key: str, default: float) -> float:
        """安全获取浮点配置"""
        try:
            return float(os.environ.get(key, str(default)))
        except (ValueError, TypeError):
            return default
    
    @classmethod
    def _validate_api_key(cls, api_key: str) -> None:
        """验证 API Key 是否配置"""
        if not api_key or api_key.strip() == "":
            raise ValueError(
                "LLM_API_KEY 未配置！\n"
                "请通过以下方式设置:\n"
                "  1. 环境变量：export LLM_API_KEY='sk-xxx'\n"
                "  2. .env 文件\n"
                "  3. 启动参数：./start.sh --llm-key 'sk-xxx'"
            )
    
    @classmethod
    @property
    def server(cls) -> ServerConfig:
        """获取服务器配置"""
        if cls._server is None:
            cls._server = ServerConfig(
                host=os.environ.get("SKILLS_HOST", "0.0.0.0"),
                port=cls._get_int("SKILLS_PORT", 8766),
                debug=os.environ.get("DEBUG", "false").lower() == "true",
            )
        return cls._server
    
    @classmethod
    @property
    def llm(cls) -> LLMConfig:
        """获取 LLM 配置"""
        if cls._llm is None:
            api_key = os.environ.get("LLM_API_KEY", "sk-c158df64ece64143b8ee42975ed5d565")
            cls._validate_api_key(api_key)
            cls._llm = LLMConfig(
                api_key=api_key.strip(),
                model=os.environ.get("LLM_MODEL", "qwen-plus"),
                timeout=cls._get_int("LLM_TIMEOUT", 180),
                temperature=cls._get_float("LLM_TEMPERATURE", 0.3),
            )
        return cls._llm
    
    @classmethod
    @property
    def task(cls) -> TaskConfig:
        """获取任务配置"""
        if cls._task is None:
            cls._task = TaskConfig(
                workers=cls._get_int("TASK_WORKERS", 3),
                max_retries=cls._get_int("MAX_RETRIES", 3),
            )
        return cls._task
    
    @classmethod
    @property
    def storage(cls) -> StorageConfig:
        """获取存储配置"""
        if cls._storage is None:
            project_root = Path(__file__).parent.parent
            data_dir = os.path.expanduser(
                os.environ.get("SKILLS_DATA_DIR", "~/.agent_skills")
            )
            log_dir = str(project_root / "logs")
            
            # 确保目录存在
            Path(data_dir).mkdir(parents=True, exist_ok=True)
            Path(log_dir).mkdir(parents=True, exist_ok=True)
            
            cls._storage = StorageConfig(
                data_dir=data_dir,
                log_dir=log_dir,
                db_path=os.path.join(data_dir, "tasks.db"),
                default_save_dir=os.path.expanduser(
                    os.environ.get("DEFAULT_SAVE_DIR", "~/Documents/ERP 需求文档")
                ),
            )
        return cls._storage
    
    @classmethod
    def reload(cls) -> None:
        """重新加载配置（用于测试）"""
        cls._server = None
        cls._llm = None
        cls._task = None
        cls._storage = None


# 兼容旧代码的快捷访问
HOST = os.environ.get("SKILLS_HOST", "0.0.0.0")
PORT = Config._get_int("SKILLS_PORT", 8766)
LLM_API_KEY = os.environ.get("LLM_API_KEY", "sk-c158df64ece64143b8ee42975ed5d565")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen-plus")
TASK_WORKERS = Config._get_int("TASK_WORKERS", 3)
MAX_RETRIES = Config._get_int("MAX_RETRIES", 3)
RETRY_INTERVALS = (15, 30, 60)
DATA_DIR = os.path.expanduser(os.environ.get("SKILLS_DATA_DIR", "~/.agent_skills"))
LOG_DIR = str(Path(__file__).parent.parent / "logs")
DB_PATH = os.path.join(DATA_DIR, "tasks.db")
DEFAULT_SAVE_DIR = os.path.expanduser(
    os.environ.get("DEFAULT_SAVE_DIR", "~/Documents/ERP 需求文档")
)

# 初始化目录
Path(DATA_DIR).mkdir(parents=True, exist_ok=True)
Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
