"""
LLM 客户端 — 通义千问 Qwen
========================
直接调用通义千问 API 生成功能点详设文档，
不再依赖 Dify 中间层，减少部署步骤。
"""

import json
import ssl
import time
import logging
import threading
import urllib.request
import urllib.error

from .config import LLM_API_KEY, LLM_MODEL

logger = logging.getLogger("agent_skills.llm_client")

# 通义千问 OpenAI 兼容接口
LLM_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

# 全局速率控制：确保并发线程不会同时调用 API
# 每次调用结束后强制等待一段时间再释放下一个请求
_api_lock = threading.Lock()
_MIN_INTERVAL = 5  # 两次 API 调用之间的最小间隔（秒）
_last_call_time = 0.0

# macOS 上 Python 可能找不到系统根证书，需要显式创建 SSL 上下文
try:
    import certifi
    _ssl_ctx = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _ssl_ctx = ssl.create_default_context()
    _ssl_ctx.check_hostname = False
    _ssl_ctx.verify_mode = ssl.CERT_NONE

SYSTEM_PROMPT = """你是资深的跨境电商ERP系统架构师兼产品经理，具备丰富的B2C/B2B跨境电商系统设计经验。
你需要针对给定的功能点，输出一份完整的功能详细设计文档，涵盖输入输出、功能设计和测试要求。

请严格按照以下 Markdown 格式输出，每个章节都必须填写具体内容，禁止省略或使用占位符：

### [功能点名称]

#### 1. 功能概述
- **业务目标**：该功能要解决什么业务问题
- **用户价值**：给用户带来什么具体价值
- **使用角色**：哪些角色会使用该功能
- **使用频率**：高频/中频/低频

#### 2. 输入参数
| 参数名 | 类型 | 必填 | 校验规则 | 说明 |
|--------|------|------|----------|------|
| (具体参数) | (具体类型) | 是/否 | (具体校验) | (具体说明) |

#### 3. 输出结果
| 输出项 | 类型 | 说明 |
|--------|------|------|
| (具体输出) | (具体类型) | (具体说明) |

#### 4. 功能设计

##### 4.1 交互流程
用文字描述用户操作的完整步骤（从进入页面到完成操作）。

##### 4.2 核心逻辑
详细描述后端处理的核心算法或业务逻辑，包括数据如何流转、关键计算规则。

##### 4.3 接口设计
| 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|
| (接口名) | GET/POST/PUT/DELETE | (路径) | (说明) |

##### 4.4 数据模型
列出该功能涉及的核心数据表或数据结构，说明关键字段。

#### 5. 业务规则
1. (具体的业务规则，至少列出3条)
2. ...

#### 6. 测试要求

##### 6.1 功能测试用例
| 编号 | 测试场景 | 前置条件 | 操作步骤 | 预期结果 | 优先级 |
|------|----------|----------|----------|----------|--------|
| TC01 | (具体场景) | (前置条件) | (步骤) | (预期) | P0/P1/P2 |

##### 6.2 边界测试
- (至少列出3个边界条件的测试点)

##### 6.3 异常场景
| 异常场景 | 触发条件 | 系统处理方式 | 用户提示 |
|----------|----------|-------------|----------|
| (具体异常) | (条件) | (处理方式) | (提示内容) |

---

要求：
1. 所有内容必须结合项目背景信息具体展开，不要写通用模板
2. 功能测试用例至少写5条，覆盖正常流程和异常流程
3. 接口设计要给出具体的请求参数和响应结构
4. 数据模型要列出具体的字段名和类型"""


def call_completion(
    feature_name: str,
    project_context: str,
    business_model: str = "",
    target_market: str = "",
    platforms: str = "",
    detail_level: str = "详细",
) -> str:
    """
    调用通义千问 API 生成单个功能点的详细设计文档。

    Returns:
        LLM 生成的 Markdown 文本
    Raises:
        Exception: API 调用失败时抛出异常
    """
    user_message = (
        f"请为以下功能点撰写完整的详细设计文档：\n\n"
        f"## 功能点名称\n{feature_name}\n\n"
        f"## 项目背景\n{project_context}\n\n"
        f"## 背景信息\n"
        f"- 业务模式：{business_model or 'B2C零售'}\n"
        f"- 目标市场：{target_market or '全球'}\n"
        f"- 对接平台：{platforms or '未指定'}\n"
        f"- 文档详细程度：{detail_level or '详细'}\n\n"
        f"请严格按照系统提示词中的格式要求输出，"
        f"所有章节都必须结合以上项目背景具体展开。"
    )

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.3,
    }

    data = json.dumps(payload).encode("utf-8")

    # 429 限流自动退避重试：最多重试 6 次，退避间隔递增
    backoff_intervals = [15, 30, 45, 60, 90, 120]
    last_error = None

    for attempt in range(len(backoff_intervals) + 1):
        # 全局速率控制：排队等待，确保两次调用间至少间隔 _MIN_INTERVAL 秒
        global _last_call_time
        with _api_lock:
            now = time.time()
            elapsed = now - _last_call_time
            if elapsed < _MIN_INTERVAL:
                wait_for = _MIN_INTERVAL - elapsed
                logger.debug("速率控制：等待 %.1f 秒", wait_for)
                time.sleep(wait_for)
            _last_call_time = time.time()

        req = urllib.request.Request(
            LLM_API_URL,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {LLM_API_KEY}",
            },
            method="POST",
        )

        logger.info("调用 LLM: model=%s, 功能点=[%s] (第%d次)", LLM_MODEL, feature_name, attempt + 1)
        try:
            resp = urllib.request.urlopen(req, timeout=180, context=_ssl_ctx)
            result = json.loads(resp.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < len(backoff_intervals):
                wait = backoff_intervals[attempt]
                logger.warning(
                    "API 限流(429)，功能点=[%s]，%d秒后第%d次重试",
                    feature_name, wait, attempt + 2,
                )
                time.sleep(wait)
                last_error = e
            else:
                raise

    raise last_error
