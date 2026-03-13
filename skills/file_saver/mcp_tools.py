"""
文件保存 Skill — MCP Tool 注册
"""

import os

from core.config import DEFAULT_SAVE_DIR
from .service import save_file


def register_mcp_tools(mcp):
    """将文件保存工具注册到 MCP Server 实例上"""

    @mcp.tool()
    def save_markdown_file(
        content: str,
        filename: str = "",
        save_directory: str = "",
    ) -> str:
        """
        将 Markdown 内容保存为文件到指定目录。

        Args:
            content: 要保存的 Markdown 文本内容
            filename: 文件名（不含路径）。留空则自动生成带时间戳的文件名。
            save_directory: 保存目录的绝对路径。留空则使用默认目录。

        Returns:
            保存结果信息
        """
        result = save_file(content, filename, save_directory)
        if result["success"]:
            return f"文件保存成功！\n路径：{result['filepath']}\n大小：{result['size']}"
        return f"错误：{result['message']}"

    @mcp.tool()
    def list_save_directories() -> str:
        """列出常用的保存目录供用户选择。"""
        home = os.path.expanduser("~")
        candidates = [
            DEFAULT_SAVE_DIR,
            os.path.join(home, "Documents"),
            os.path.join(home, "Desktop"),
            os.path.join(home, "Downloads"),
        ]
        lines = ["可选的保存目录：", ""]
        for i, d in enumerate(candidates, 1):
            exists = "已存在" if os.path.isdir(d) else "将自动创建"
            lines.append(f"  {i}. {d}  ({exists})")
        lines.append("")
        lines.append("也可以输入任意绝对路径作为保存目录。")
        return "\n".join(lines)
