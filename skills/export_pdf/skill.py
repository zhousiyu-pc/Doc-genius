"""
PDF 导出 Skill（使用 reportlab）
==============================
将合并后的 Markdown 转为 PDF 文件并保存到会话导出目录。
使用 reportlab（纯 Python）替代 xhtml2pdf，避免系统依赖。
支持将 Mermaid 代码块渲染为 PNG 图片，嵌入文档末尾附件章节。
"""

import os
import re
import logging
from typing import List, Tuple

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.platypus import Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_LEFT

from skills.export_utils import get_export_dir, build_combined_markdown

logger = logging.getLogger("agent_skills.export_pdf")

# 尝试注册系统中文字体（macOS PingFang / Windows SimSun）
_CJK_FONT = "Helvetica"
_CJK_FONT_BOLD = "Helvetica-Bold"

try:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    _FONT_CANDIDATES = [
        # macOS
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        # Linux
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    for font_path in _FONT_CANDIDATES:
        if os.path.isfile(font_path):
            pdfmetrics.registerFont(TTFont("CJKFont", font_path, subfontIndex=0))
            _CJK_FONT = "CJKFont"
            _CJK_FONT_BOLD = "CJKFont"
            logger.info("PDF 中文字体已注册: %s", font_path)
            break
    else:
        logger.warning("未找到系统中文字体，PDF 中文可能显示为方框")
except Exception as exc:
    logger.warning("注册中文字体失败: %s，使用默认字体", exc)


def _build_styles() -> dict:
    """构建 PDF 样式集合。"""
    base = getSampleStyleSheet()
    styles = {}
    styles["title"] = ParagraphStyle(
        "PDFTitle",
        parent=base["Title"],
        fontName=_CJK_FONT_BOLD,
        fontSize=18,
        leading=24,
        spaceAfter=12,
    )
    styles["h1"] = ParagraphStyle(
        "PDFH1",
        parent=base["Heading1"],
        fontName=_CJK_FONT_BOLD,
        fontSize=16,
        leading=22,
        spaceBefore=14,
        spaceAfter=8,
    )
    styles["h2"] = ParagraphStyle(
        "PDFH2",
        parent=base["Heading2"],
        fontName=_CJK_FONT_BOLD,
        fontSize=13,
        leading=18,
        spaceBefore=10,
        spaceAfter=6,
    )
    styles["h3"] = ParagraphStyle(
        "PDFH3",
        parent=base["Heading3"],
        fontName=_CJK_FONT_BOLD,
        fontSize=11,
        leading=15,
        spaceBefore=8,
        spaceAfter=4,
    )
    styles["body"] = ParagraphStyle(
        "PDFBody",
        parent=base["Normal"],
        fontName=_CJK_FONT,
        fontSize=10,
        leading=15,
        spaceAfter=4,
        alignment=TA_LEFT,
    )
    return styles


def _escape_xml(text: str) -> str:
    """转义 XML 特殊字符，避免 reportlab 解析失败。"""
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    return text


def _md_to_flowables(md_text: str, styles: dict) -> list:
    """将 Markdown 文本转换为 reportlab flowable 列表。"""
    flowables = []
    lines = md_text.split("\n")

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flowables.append(Spacer(1, 4 * mm))
            continue
        if stripped.startswith("---"):
            flowables.append(Spacer(1, 6 * mm))
            continue

        # 标题匹配
        heading_match = re.match(r"^(#{1,3})\s+(.+)$", stripped)
        if heading_match:
            level = len(heading_match.group(1))
            text = _escape_xml(heading_match.group(2))
            style_key = f"h{level}"
            flowables.append(Paragraph(text, styles.get(style_key, styles["h3"])))
            continue

        # 列表项
        list_match = re.match(r"^[-*]\s+(.+)$", stripped)
        if list_match:
            text = _escape_xml(list_match.group(1))
            flowables.append(Paragraph(f"• {text}", styles["body"]))
            continue

        # 有序列表
        ordered_match = re.match(r"^\d+\.\s+(.+)$", stripped)
        if ordered_match:
            text = _escape_xml(ordered_match.group(1))
            flowables.append(Paragraph(f"  {text}", styles["body"]))
            continue

        # 普通段落
        text = _escape_xml(stripped)
        # 简单处理加粗（** **）
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        flowables.append(Paragraph(text, styles["body"]))

    return flowables


def export_to_pdf(
    session_id: str,
    project_name: str,
    contents: List[Tuple[str, str]],
    filename_suffix: str = "_需求与详设",
) -> Tuple[bool, str, str]:
    """
    将多段 (标题, Markdown内容) 合并并导出为 PDF。
    自动检测 Mermaid 代码块并渲染为 PNG 图片，放入文档末尾附件章节。

    Returns:
        (success, file_path, error_message)
    """
    export_dir = get_export_dir(session_id)
    filename = f"{project_name or 'document'}{filename_suffix}.pdf"
    filename = _sanitize_filename(filename)
    file_path = os.path.join(export_dir, filename)

    try:
        combined_md = build_combined_markdown(contents, project_name)

        # Mermaid 预处理：提取代码块并渲染为 PNG
        mermaid_images: list[tuple[str, str]] = []
        try:
            from skills.mermaid_renderer import extract_and_render_mermaid
            img_dir = os.path.join(export_dir, "images")
            combined_md, mermaid_images = extract_and_render_mermaid(combined_md, img_dir)
        except Exception as mermaid_exc:
            logger.warning("Mermaid 预处理失败（保留原始代码块）: %s", mermaid_exc)

        styles = _build_styles()
        flowables = _md_to_flowables(combined_md, styles)

        if not flowables:
            return False, "", "无内容可导出"

        # 在 PDF 末尾添加附件章节（Mermaid 渲染的 PNG 图片）
        if mermaid_images:
            flowables.append(PageBreak())
            flowables.append(Paragraph("附件", styles["h1"]))
            flowables.append(Spacer(1, 6 * mm))

            for img_title, img_path in mermaid_images:
                if os.path.isfile(img_path):
                    flowables.append(Paragraph(f"图: {_escape_xml(img_title)}", styles["h3"]))
                    flowables.append(Spacer(1, 3 * mm))
                    try:
                        # 限制图片宽度为页面可用宽度（A4 - 左右边距）
                        max_width = A4[0] - 40 * mm
                        img = RLImage(img_path)
                        # 等比缩放
                        iw, ih = img.drawWidth, img.drawHeight
                        if iw > max_width:
                            ratio = max_width / iw
                            img.drawWidth = max_width
                            img.drawHeight = ih * ratio
                        flowables.append(img)
                    except Exception as img_exc:
                        logger.warning("PDF 插入图片失败 (%s): %s", img_path, img_exc)
                        flowables.append(Paragraph(
                            f"[图片加载失败: {_escape_xml(img_title)}]", styles["body"]
                        ))
                    flowables.append(Spacer(1, 8 * mm))

        doc = SimpleDocTemplate(
            file_path,
            pagesize=A4,
            leftMargin=20 * mm,
            rightMargin=20 * mm,
            topMargin=20 * mm,
            bottomMargin=20 * mm,
        )
        doc.build(flowables)
        logger.info("PDF 已保存: %s", file_path)
        return True, file_path, ""
    except Exception as exc:
        logger.exception("PDF 导出失败: %s", exc)
        return False, "", str(exc)


def _sanitize_filename(name: str) -> str:
    """移除文件名中的非法字符。"""
    for c in ["/", "\\", ":", "*", "?", '"', "<", ">", "|"]:
        name = name.replace(c, "_")
    return name[:200] if len(name) > 200 else name
