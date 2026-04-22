"""智能分块模块

基于 LLM 的 One-Pass 分块：语义分块 + 指代消解 + 假设问题生成（HyDE）+ 图谱关系提取
"""

from knowlebase.chunker.models import ChunkResult, Relation
from knowlebase.chunker.langchain_chunker import LangChainChunker, chunk_document
from knowlebase.chunker.image_describer import replace_images_with_markers

__all__ = ["ChunkResult", "Relation", "LangChainChunker", "chunk_document", "replace_images_with_markers"]
