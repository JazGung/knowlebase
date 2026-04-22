"""分块结果数据模型"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Relation:
    """图关系三元组"""
    source: str
    relationship: str
    target: str


@dataclass
class ChunkResult:
    """单个分块的结果"""

    original_text: str
    """还原图片为 [IMAGE: path|caption] 占位符，前端可通过 path 预览图片"""

    processed_text: str
    """含重叠前缀 + 完整图片描述 + 指代消解，用于向量入库和检索"""

    hypothetical_questions: List[str] = field(default_factory=list)
    """假设问题列表（HyDE），用于增强检索"""

    relations: List[Relation] = field(default_factory=list)
    """图关系三元组列表"""

    page_range: Optional[str] = None
    """页码范围，如 '1-3' 或 '5'"""

    section_title: Optional[str] = None
    """所属章节标题"""
