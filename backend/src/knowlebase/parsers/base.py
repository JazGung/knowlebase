"""文档解析器基础模块

定义解析结果数据结构和抽象基类
"""

from dataclasses import dataclass, field
from typing import List, Optional, Union
from abc import ABC, abstractmethod


@dataclass
class ParsedText:
    """纯文本段落"""
    type: str = "text"
    text: str = ""
    page_number: Optional[int] = None


@dataclass
class ParsedImage:
    """图片"""
    type: str = "image"
    image_path: str = ""  # MinIO 对象路径
    caption: str = ""
    page_number: Optional[int] = None


@dataclass
class ParsedTable:
    """表格"""
    type: str = "table"
    headers: List[str] = field(default_factory=list)
    rows: List[List[str]] = field(default_factory=list)
    page_number: Optional[int] = None


@dataclass
class ParsedSection:
    """子章节"""
    type: str = "section"
    title: str = ""
    content: List[Union["ParsedText", "ParsedImage", "ParsedTable", "ParsedSection"]] = field(default_factory=list)


@dataclass
class ParseResult:
    """解析结果"""
    sections: List[ParsedSection] = field(default_factory=list)
    page_count: int = 0
    has_images: bool = False
    has_tables: bool = False


class BaseParser(ABC):
    """文档解析器抽象基类"""

    @abstractmethod
    async def parse(self, content: bytes) -> ParseResult:
        """解析文档内容

        Args:
            content: 文档原始字节内容

        Returns:
            ParseResult: 解析结果
        """
        pass
