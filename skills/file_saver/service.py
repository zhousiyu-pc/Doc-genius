"""
文件保存 Skill
==============
提供 Markdown 文件保存能力，支持 MCP 协议和 REST API 两种接入方式。
"""

import os
import re
import datetime
import logging
from pathlib import Path

from core.config import DEFAULT_SAVE_DIR

logger = logging.getLogger("agent_skills.file_saver")


def sanitize_filename(name: str) -> str:
    """清理文件名中的非法字符"""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
    cleaned = cleaned.strip('. ')
    return cleaned if cleaned else 'unnamed'


def save_file(content: str, filename: str = "", save_directory: str = "") -> dict:
    """
    核心保存逻辑。

    Returns:
        dict 包含 success, message, filepath, filename, size 等字段
    """
    if not content or not content.strip():
        return {"success": False, "message": "内容为空，无法保存。"}

    target_dir = save_directory.strip() if save_directory else DEFAULT_SAVE_DIR
    target_dir = os.path.expanduser(target_dir)

    if not filename or not filename.strip():
        now = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"ERP需求文档_{now}.md"
    else:
        filename = sanitize_filename(filename.strip())
        if not filename.endswith('.md'):
            filename += '.md'

    try:
        Path(target_dir).mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return {"success": False, "message": f"无法创建目录 {target_dir}：{e}"}

    filepath = os.path.join(target_dir, filename)
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    except OSError as e:
        return {"success": False, "message": f"无法写入文件 {filepath}：{e}"}

    file_size = os.path.getsize(filepath)
    size_display = (
        f"{file_size / 1024:.1f} KB"
        if file_size < 1024 * 1024
        else f"{file_size / (1024 * 1024):.2f} MB"
    )

    logger.info("文件保存成功: %s (%s)", filepath, size_display)

    return {
        "success": True,
        "message": "文件保存成功",
        "filepath": filepath,
        "filename": filename,
        "size": size_display,
    }
