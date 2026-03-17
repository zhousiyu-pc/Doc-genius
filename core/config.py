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


# 各 LLM 提供商的默认 API URL
LLM_PROVIDER_URLS = {
    "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    "openai": "https://api.openai.com/v1/chat/completions",
    "deepseek": "https://api.deepseek.com/v1/chat/completions",
    "anthropic": "https://api.anthropic.com/v1/messages",
}

# 可用模型列表（带分级和成本估算）
AVAILABLE_MODELS = [
    {"id": "qwen-plus", "name": "通义千问 Plus", "provider": "dashscope", "tier": "base", "cost_multiplier": 1.0},
    {"id": "deepseek-chat", "name": "DeepSeek Chat", "provider": "deepseek", "tier": "base", "cost_multiplier": 0.5},
    {"id": "qwen-max", "name": "通义千问 Max", "provider": "dashscope", "tier": "advanced", "cost_multiplier": 4.0},
    {"id": "gpt-4o", "name": "GPT-4o", "provider": "openai", "tier": "advanced", "cost_multiplier": 7.5},
    {"id": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6", "provider": "anthropic", "tier": "advanced", "cost_multiplier": 7.5},
    {"id": "claude-opus-4-6", "name": "Claude Opus 4.6", "provider": "anthropic", "tier": "premium", "cost_multiplier": 37.5},
    {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "provider": "openai", "tier": "base", "cost_multiplier": 0.8},
    {"id": "deepseek-reasoner", "name": "DeepSeek Reasoner", "provider": "deepseek", "tier": "advanced", "cost_multiplier": 2.0},
    {"id": "qwen-turbo", "name": "通义千问 Turbo", "provider": "dashscope", "tier": "base", "cost_multiplier": 0.3},
]

# 套餐级别可访问的模型 tier
PLAN_MODEL_ACCESS = {
    "free": ["base"],
    "pro": ["base", "advanced"],
    "team": ["base", "advanced", "premium"],
    "enterprise": ["base", "advanced", "premium"],
}


@dataclass(frozen=True)
class LLMConfig:
    """LLM 配置"""
    api_key: str
    model: str = "qwen-plus"
    provider: str = "dashscope"
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
        """验证 API Key 是否配置（仅警告，不强制）"""
        if not api_key or api_key.strip() == "":
            import logging
            logging.getLogger("agent_skills.config").warning(
                "LLM_API_KEY 未配置！LLM 功能将不可用。\n"
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
            api_key = os.environ.get("LLM_API_KEY", "")
            cls._validate_api_key(api_key)
            provider = os.environ.get("LLM_PROVIDER", "dashscope").lower()
            default_url = LLM_PROVIDER_URLS.get(
                provider,
                LLM_PROVIDER_URLS["dashscope"],
            )
            api_url = os.environ.get("LLM_API_URL", default_url)
            cls._llm = LLMConfig(
                api_key=api_key.strip(),
                model=os.environ.get("LLM_MODEL", "qwen-plus"),
                provider=provider,
                api_url=api_url,
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
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen-plus")
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "dashscope").lower()
LLM_API_URL = os.environ.get(
    "LLM_API_URL",
    LLM_PROVIDER_URLS.get(LLM_PROVIDER, LLM_PROVIDER_URLS["dashscope"]),
)
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
