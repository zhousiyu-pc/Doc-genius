"""
导出工具 — 会话导出目录与合并文档
================================
为 PDF/Word/PPT 导出 Skill 提供统一的目录与合并逻辑。
"""

import os
import logging
from pathlib import Path
from typing import List, Tuple

from core.config import DATA_DIR

logger = logging.getLogger("agent_skills.export_utils")

EXPORTS_SUBDIR = "exports"


def get_export_dir(session_id: str) -> str:
    """
    获取某会话的导出文件目录，不存在则创建。
    路径: {DATA_DIR}/exports/{session_id}/
    """
    path = os.path.join(DATA_DIR, EXPORTS_SUBDIR, session_id)
    Path(path).mkdir(parents=True, exist_ok=True)
    return path


def build_combined_markdown(contents: List[Tuple[str, str]], project_name: str = "") -> str:
    """
    将多段 (标题, 内容) 合并为一份 Markdown 文档。

    Args:
        contents: [(display_name, content), ...]
        project_name: 用于文档大标题
    """
    parts = [f"# {project_name} — 需求与详设文档\n\n"] if project_name else []
    for title, body in contents:
        if not body or not body.strip():
            continue
        parts.append(f"## {title}\n\n")
        parts.append(body.strip())
        parts.append("\n\n---\n\n")
    return "".join(parts)
