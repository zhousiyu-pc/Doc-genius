"""
Mermaid 图表渲染工具
==================
提供将 Mermaid 代码转为 PNG 图片的能力，供导出 Word/PDF 时使用。
使用 @mermaid-js/mermaid-cli (mmdc) 命令行工具进行服务端渲染。

功能：
- render_mermaid_to_png: 将单段 Mermaid 代码渲染为 PNG 文件
- extract_and_render_mermaid: 从 Markdown 中提取所有 Mermaid 代码块，
  渲染为 PNG 并替换原文中的代码块为引用文字
"""

import os
import re
import uuid
import shutil
import logging
import tempfile
import subprocess
from typing import Optional

logger = logging.getLogger("agent_skills.mermaid_renderer")

# Mermaid 代码块正则：匹配 ```mermaid ... ```
_MERMAID_BLOCK_PATTERN = re.compile(
    r"```mermaid\s*\n(.*?)```",
    re.DOTALL,
)

# 项目根目录下的 node_modules/.bin/mmdc
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MMDC_LOCAL = os.path.join(_PROJECT_ROOT, "node_modules", ".bin", "mmdc")

# Node.js 18 路径（通过 nvm 安装）
_NODE18_BIN = os.path.expanduser("~/.nvm/versions/node/v18.20.8/bin")


def _find_mmdc() -> Optional[str]:
    """
    查找 mmdc 可执行文件路径。
    优先使用项目本地安装的 mmdc，其次查找全局 mmdc。

    Returns:
        mmdc 路径，找不到时返回 None
    """
    if os.path.isfile(_MMDC_LOCAL) and os.access(_MMDC_LOCAL, os.X_OK):
        return _MMDC_LOCAL

    mmdc_path = shutil.which("mmdc")
    if mmdc_path:
        return mmdc_path

    # 尝试 Node 18 路径下的 mmdc
    node18_mmdc = os.path.join(_NODE18_BIN, "mmdc")
    if os.path.isfile(node18_mmdc):
        return node18_mmdc

    return None


def render_mermaid_to_png(mermaid_code: str, output_path: str) -> bool:
    """
    调用 mmdc CLI 将一段 Mermaid 代码渲染为 PNG 图片。

    Args:
        mermaid_code: Mermaid 图表源码
        output_path: PNG 文件保存路径

    Returns:
        渲染是否成功
    """
    mmdc = _find_mmdc()
    if not mmdc:
        logger.warning("未找到 mmdc 命令，跳过 Mermaid 渲染。请运行 npm install @mermaid-js/mermaid-cli")
        return False

    tmp_dir = tempfile.mkdtemp(prefix="mermaid_")
    input_file = os.path.join(tmp_dir, "input.mmd")

    try:
        with open(input_file, "w", encoding="utf-8") as f:
            f.write(mermaid_code)

        # 构建 PATH，确保 Node 18 可用
        env = os.environ.copy()
        if os.path.isdir(_NODE18_BIN):
            env["PATH"] = _NODE18_BIN + os.pathsep + env.get("PATH", "")

        result = subprocess.run(
            [mmdc, "-i", input_file, "-o", output_path, "-b", "white", "-s", "2"],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )

        if result.returncode == 0 and os.path.isfile(output_path):
            logger.info("Mermaid 渲染成功: %s", output_path)
            return True
        else:
            logger.warning(
                "Mermaid 渲染失败 (exit=%d): stdout=%s, stderr=%s",
                result.returncode, result.stdout[:200], result.stderr[:200],
            )
            return False

    except subprocess.TimeoutExpired:
        logger.warning("Mermaid 渲染超时（30秒）: %s", output_path)
        return False
    except Exception as exc:
        logger.exception("Mermaid 渲染异常: %s", exc)
        return False
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


def extract_and_render_mermaid(
    markdown_text: str,
    output_dir: str,
) -> tuple[str, list[tuple[str, str]]]:
    """
    从 Markdown 文本中提取所有 ```mermaid 代码块，逐个渲染为 PNG 图片。

    处理逻辑：
    1. 扫描所有 ```mermaid ... ``` 代码块
    2. 对每个代码块调用 mmdc 渲染为 PNG
    3. 在原文中将代码块替换为引用文字（如 "（详见附件 图1: 流程图）"）
    4. 渲染失败的代码块保留原始 Mermaid 源码不变

    Args:
        markdown_text: 原始 Markdown 文本（可能包含多个 mermaid 代码块）
        output_dir: PNG 图片保存目录

    Returns:
        (cleaned_markdown, images):
        - cleaned_markdown: 替换后的 Markdown 文本
        - images: [(图片标题, 图片路径), ...] 列表
    """
    os.makedirs(output_dir, exist_ok=True)
    matches = list(_MERMAID_BLOCK_PATTERN.finditer(markdown_text))

    if not matches:
        return markdown_text, []

    images: list[tuple[str, str]] = []
    cleaned = markdown_text
    offset = 0

    for idx, match in enumerate(matches, start=1):
        mermaid_code = match.group(1).strip()

        # 尝试从 Mermaid 代码中推断图表类型作为标题
        diagram_title = _infer_diagram_title(mermaid_code, idx)

        img_filename = f"diagram_{idx}_{uuid.uuid4().hex[:6]}.png"
        img_path = os.path.join(output_dir, img_filename)

        success = render_mermaid_to_png(mermaid_code, img_path)

        if success:
            replacement = f"\n\n> （详见附件 图{idx}: {diagram_title}）\n\n"
            images.append((diagram_title, img_path))
        else:
            # 渲染失败时保留原始代码块
            replacement = match.group(0)

        # 执行替换（考虑偏移量）
        start = match.start() + offset
        end = match.end() + offset
        cleaned = cleaned[:start] + replacement + cleaned[end:]
        offset += len(replacement) - (match.end() - match.start())

    logger.info("Mermaid 提取完成: 共 %d 个代码块, 成功渲染 %d 个", len(matches), len(images))
    return cleaned, images


def _infer_diagram_title(mermaid_code: str, index: int) -> str:
    """
    根据 Mermaid 代码内容推断图表标题。

    Args:
        mermaid_code: Mermaid 源码
        index: 图表序号（用于兜底标题）

    Returns:
        推断出的图表标题
    """
    first_line = mermaid_code.split("\n")[0].strip().lower()
    if first_line.startswith("flowchart") or first_line.startswith("graph"):
        return "流程图"
    elif first_line.startswith("sequencediagram"):
        return "时序图"
    elif first_line.startswith("erdiagram"):
        return "ER 图"
    elif first_line.startswith("classDiagram"):
        return "类图"
    elif first_line.startswith("gantt"):
        return "甘特图"
    elif first_line.startswith("pie"):
        return "饼图"
    elif first_line.startswith("statediagram"):
        return "状态图"
    else:
        return f"图表{index}"
