"""PDF 文档解析器

使用 pdfplumber 提取纯文本。
按页面提取文本，通过 y 坐标识别段落边界，保留 page_number 信息。
"""

import logging
from io import BytesIO
from typing import List

from knowlebase.parsers.base import (
    BaseParser,
    ParsedSection,
    ParsedText,
    ParseResult,
)

logger = logging.getLogger(__name__)


class PDFParser(BaseParser):
    """PDF 解析器（pdfplumber 纯文本提取）"""

    async def parse(self, content: bytes) -> ParseResult:
        """解析 PDF 文件

        逐页提取文本，使用 pdfplumber 获取每个文本块的坐标信息，
        按 y 坐标间距聚类识别段落，每页的段落作为独立的 ParsedText。
        空白页会被跳过。
        """
        try:
            import pdfplumber
        except ImportError:
            logger.error("pdfplumber 未安装，请运行: pip install pdfplumber")
            raise

        pdf = pdfplumber.open(BytesIO(content))
        page_count = len(pdf.pages)

        content_items: List[ParsedText] = []
        for i, page in enumerate(pdf.pages):
            page_text = self._extract_page_text(page)
            page_text = page_text.strip()
            if not page_text:
                continue
            content_items.append(
                ParsedText(text=page_text, page_number=i + 1)
            )

        pdf.close()

        sections = [
            ParsedSection(title="", content=content_items)
        ]

        return ParseResult(
            sections=sections,
            page_count=page_count,
            has_images=False,
            has_tables=False,
        )

    def _extract_page_text(self, page) -> str:
        """从单页提取文本

        使用 pdfplumber 的 extract_text 方法，默认会按坐标排序，
        自然形成从上到下、从左到右的阅读顺序。
        """
        # 简单方案：直接获取整页文本
        text = page.extract_text()
        if text:
            return text

        # 如果 extract_text 返回空，尝试逐字符提取（处理特殊 PDF）
        words = page.extract_words()
        if not words:
            return ""

        # 按 y 坐标（从上到下）和 x 坐标（从左到右）排序
        words.sort(key=lambda w: (-w["top"], w["x0"]))

        lines: dict = {}
        for word in words:
            # 用 y 坐标分组（容差 3pt）
            y_key = round(word["top"] / 3) * 3
            if y_key not in lines:
                lines[y_key] = []
            lines[y_key].append(word["text"])

        # 合并为文本
        result_lines = []
        for y_key in sorted(lines.keys()):
            line_text = " ".join(lines[y_key])
            result_lines.append(line_text)

        return "\n".join(result_lines)
