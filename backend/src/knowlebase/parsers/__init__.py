"""文档解析器包

提供统一的文档解析入口，根据文件类型自动选择对应解析器。
"""

from knowlebase.parsers.base import (
    BaseParser,
    ParsedImage,
    ParsedSection,
    ParsedTable,
    ParsedText,
    ParseResult,
)
from knowlebase.parsers.pdf_parser import PDFParser
from knowlebase.parsers.docx_parser import DOCXParser

__all__ = [
    "parse_document",
    "BaseParser",
    "ParseResult",
    "ParsedText",
    "ParsedImage",
    "ParsedTable",
    "ParsedSection",
    "PDFParser",
    "DOCXParser",
]

# 文件扩展名 → 解析器映射
_PARSERS = {
    ".pdf": PDFParser,
    ".docx": DOCXParser,
    ".doc": DOCXParser,  # .doc 也尝试用 python-docx 解析
}


def _get_parser_for_filename(filename: str) -> BaseParser:
    """根据文件扩展名选择解析器"""
    ext = "." + filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    parser_cls = _PARSERS.get(ext)
    if parser_cls is None:
        raise ValueError(f"不支持的文件格式: {ext or '无扩展名'}，支持的格式: {', '.join(_PARSERS.keys())}")
    return parser_cls()


def _get_parser_for_mime_type(mime_type: str) -> BaseParser:
    """根据 MIME 类型选择解析器"""
    mime_map = {
        "application/pdf": PDFParser,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": DOCXParser,
        "application/msword": DOCXParser,
    }
    parser_cls = mime_map.get(mime_type)
    if parser_cls is None:
        raise ValueError(f"不支持的 MIME 类型: {mime_type}")
    return parser_cls()


async def parse_document(content: bytes, filename: str = "", mime_type: str = "") -> ParseResult:
    """解析文档的统一入口

    Args:
        content: 文档原始字节内容
        filename: 文件名（用于扩展名推断解析器）
        mime_type: MIME 类型（备选解析器推断方式）

    Returns:
        ParseResult: 解析结果

    Raises:
        ValueError: 不支持的文件格式时抛出
    """
    # 优先用文件名推断，其次用 MIME 类型
    if filename:
        parser = _get_parser_for_filename(filename)
    elif mime_type:
        parser = _get_parser_for_mime_type(mime_type)
    else:
        raise ValueError("需要提供 filename 或 mime_type 以确定解析器")

    return await parser.parse(content)
