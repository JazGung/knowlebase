"""基于 LangChain 的窗口滑动智能分块

每窗口一次 LLM 调用，Pipeline 处理：语义分块 + 指代消解 + HyDE + 关系提取
"""

import logging
import math
import re
from typing import List, Optional, Tuple

from knowlebase.core.config import settings
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from knowlebase.chunker.models import ChunkResult, Relation
from knowlebase.chunker.image_describer import (
    IMAGE_MARKER_START,
    IMAGE_MARKER_END,
)
from knowlebase.parsers.base import ParsedSection, ParsedText

logger = logging.getLogger(__name__)

# 图片标记正则
_IMAGE_MARKER_RE = re.compile(
    re.escape("[IMAGE_START:") + r"([^\]]*)\](.*?)\[IMAGE_END\]",
    re.DOTALL
)

# 句子结束边界
_SENTENCE_END_RE = re.compile(r"[。！？.!?\n]")


CHUNKING_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """你是一个文档处理专家。请对输入的文档内容进行以下处理：

1. **语义分块**：将文档按语义分割为多个段落。
   - 每块字数：不少于 {min_chars} 字，不超过 {max_chars} 字
   - 保持章节结构完整
   - `[IMAGE_START]...[IMAGE_END]` 包裹的内容视为原子单元，不可拆分

2. **指代消解**：将每个分块中的代词（如"它"、"该"、"其"、"这"、"那"等）替换为具体的实体名称。
   - 参考 Context 中的重叠文本和已有实体来理解代词所指

3. **假设问题生成（HyDE）**：为每个分块生成 2-5 个假设性问题

4. **关系提取**：提取实体关系三元组 (source, relationship, target)

请以 JSON 格式输出：
```json
{{
  "chunks": [
    {{
      "original_text": "原始文本（不修改任何字符）",
      "processed_text": "指代消解后的文本",
      "questions": ["问题1", "问题2"],
      "triplets": [
        {{"source": "A", "relationship": "关系", "target": "B"}}
      ]
    }}
  ]
}}
```

注意：
- original_text 必须与输入一致，一个字都不能改
- 如果文本很短（≤ {max_chars} 字），作为一个整体处理即可
- triplets 只提取文档中明确提及的实体关系"""),
    ("human", """{context_section}

章节标题：{section_title}

文档内容：
{text}"""),
])


def create_llm():
    """创建 LLM 实例"""
    from langchain.chat_models import init_chat_model

    cfg = settings.get_chunking_llm_config()
    kwargs = {
        "model": cfg["model"],
        "model_provider": "openai",
        "api_key": cfg["api_key"],
        "temperature": 0,
    }
    if cfg["api_base"]:
        kwargs["base_url"] = cfg["api_base"]

    return init_chat_model(**kwargs)


class LangChainChunker:
    """基于 LangChain 的分块器"""

    def __init__(self, llm: Optional[BaseChatModel] = None, chain=None):
        if chain is not None:
            self.chain = chain
        else:
            if llm is None:
                llm = create_llm()
            self.llm = llm
            self.chain = CHUNKING_PROMPT | self.llm | JsonOutputParser()

        self.chunk_params = settings.get_chunk_params()

    async def chunk(
        self,
        sections: List[ParsedSection],
        metadata: Optional[dict] = None,
    ) -> List[ChunkResult]:
        results: List[ChunkResult] = []

        for section in sections:
            if not section.content:
                continue

            texts = []
            for item in section.content:
                if isinstance(item, ParsedText):
                    texts.append(item)

            if not texts:
                continue

            combined_text = "\n\n".join(t.text for t in texts)
            page_numbers = [t.page_number for t in texts if t.page_number is not None]
            page_range = self._format_page_range(page_numbers)

            section_results = await self._process_section(
                section.title or "无标题",
                combined_text,
                page_range,
            )
            results.extend(section_results)

        return results

    async def _process_section(
        self,
        section_title: str,
        text: str,
        page_range: Optional[str],
    ) -> List[ChunkResult]:
        """处理单个 section，使用窗口滑动"""
        results: List[ChunkResult] = []
        params = self.chunk_params
        max_chars = params["max_chars"]
        min_chars = params["min_chars"]
        overlap = params["overlap"]
        window = params["window"]

        # 如果文本 ≤ max_chars，不再分块，整段处理
        if len(text) <= max_chars:
            llm_result = await self.chain.ainvoke({
                "context_section": "",
                "section_title": section_title,
                "min_chars": min_chars,
                "max_chars": max_chars,
                "text": text,
            })
            for chunk_data in llm_result.get("chunks", []):
                results.append(self._build_chunk_result(
                    chunk_data, section_title, page_range, ""
                ))
            return results

        # 窗口滑动
        pos = 0
        prev_processed_text = ""
        prev_entities: List[str] = []
        is_last_window = False

        while pos < len(text):
            # 确定 Current Window
            end = min(pos + window, len(text))
            window_text = text[pos:end]

            # 前溯到句子/图片/表格行边界
            window_text, boundary_offset = self._backtrack_to_boundary(
                text, pos, end, window_text
            )
            actual_end = pos + len(window_text)

            # 构建 Context
            context_parts = []
            if prev_processed_text:
                # 提取重叠部分
                overlap_text = self._extract_overlap_text(prev_processed_text, overlap)
                if overlap_text:
                    context_parts.append(f"重叠上下文：{overlap_text}")
            if prev_entities:
                context_parts.append(f"上一分块提取的实体：{', '.join(prev_entities)}")
            context_section = "\n".join(context_parts) if context_parts else ""

            # 检查是否为最后一个窗口
            if actual_end >= len(text):
                is_last_window = True

            # 调用 LLM
            llm_result = await self.chain.ainvoke({
                "context_section": context_section,
                "section_title": section_title,
                "min_chars": min_chars,
                "max_chars": max_chars,
                "text": window_text,
            })

            chunk_datas = llm_result.get("chunks", [])

            # 丢弃最后一个 chunk（边界截断风险），最后一个窗口除外
            if not is_last_window and len(chunk_datas) > 1:
                chunk_datas = chunk_datas[:-1]

            for i, chunk_data in enumerate(chunk_datas):
                # 去重：第一个 chunk 如果与前一个 chunk 重叠度过高则丢弃
                if i == 0 and results:
                    prev_original = results[-1].original_text.replace("[图片:", "[IMAGE:").split("|")[0] if "[图片:" in results[-1].original_text else ""
                    curr_original = chunk_data.get("original_text", "")
                    if self._overlap_ratio(prev_original, curr_original) > 0.8:
                        continue

                results.append(self._build_chunk_result(
                    chunk_data, section_title, page_range, ""
                ))

            # 更新状态
            if chunk_datas:
                last_chunk = chunk_datas[-1]
                prev_processed_text = last_chunk.get("processed_text", "")
                # 提取实体
                prev_entities = []
                for t in last_chunk.get("triplets", []):
                    src = t.get("source", "")
                    tgt = t.get("target", "")
                    if src and src not in prev_entities:
                        prev_entities.append(src)
                    if tgt and tgt not in prev_entities:
                        prev_entities.append(tgt)

            pos = actual_end

        return results

    def _build_chunk_result(
        self,
        chunk_data: dict,
        section_title: str,
        page_range: Optional[str],
        overlap_prefix: str,
    ) -> ChunkResult:
        original = chunk_data.get("original_text", "")
        processed = chunk_data.get("processed_text", "")

        # 还原 original_text 中的图片占位符
        original_restored = self._restore_image_placeholders(original)

        # processed_text 添加重叠前缀
        if overlap_prefix:
            processed = overlap_prefix + processed

        # 提取实体关系
        relations = []
        for t in chunk_data.get("triplets", []):
            relations.append(Relation(
                source=t.get("source", ""),
                relationship=t.get("relationship", ""),
                target=t.get("target", ""),
            ))

        return ChunkResult(
            original_text=original_restored,
            processed_text=processed,
            hypothetical_questions=chunk_data.get("questions", []),
            relations=relations,
            page_range=page_range,
            section_title=section_title,
        )

    def _restore_image_placeholders(self, text: str) -> str:
        """将 [IMAGE_START:caption]描述[IMAGE_END] 替换为 [IMAGE: path=xxx|caption=xxx]"""
        def replacer(match):
            caption = match.group(1)
            return f"[IMAGE: path=images/placeholder.png|caption={caption}]"
        return _IMAGE_MARKER_RE.sub(replacer, text)

    def _extract_overlap_text(self, processed_text: str, overlap: int) -> str:
        """从 processed_text 末尾提取至少 overlap 长度的完整句子"""
        if len(processed_text) <= overlap:
            return processed_text

        suffix = processed_text[-overlap:]
        # 向前找句子边界
        idx = -1
        for m in _SENTENCE_END_RE.finditer(suffix):
            idx = m.end()
        if idx > 0:
            return processed_text[-(len(suffix) - idx):]
        return processed_text[-overlap:]

    def _backtrack_to_boundary(
        self, full_text: str, start: int, end: int, window_text: str
    ) -> Tuple[str, int]:
        """将窗口边界前溯到句子/图片/表格行之前"""
        if end >= len(full_text):
            return window_text, 0

        # 检查是否切到了图片标记中间
        if "[IMAGE_START:" in full_text[start:end] or "[IMAGE_END]" in full_text[start:end]:
            # 整个窗口内如果有完整图片标记，确保不切割
            pass

        # 前溯找句子边界
        search_text = full_text[start:end]
        # 从窗口开头向前找句子结束标记
        backtrack_start = max(0, start - 200)
        before_text = full_text[backtrack_start:start]

        last_sent_end = 0
        for m in _SENTENCE_END_RE.finditer(before_text):
            last_sent_end = m.end()

        if last_sent_end > 0:
            offset = backtrack_start + last_sent_end
            return full_text[offset:end], offset - start

        return window_text, 0

    def _overlap_ratio(self, text_a: str, text_b: str) -> float:
        """计算两个文本的重叠度"""
        if not text_a or not text_b:
            return 0.0
        shorter = text_a if len(text_a) <= len(text_b) else text_b
        longer = text_b if len(text_a) <= len(text_b) else text_a
        if shorter in longer:
            return len(shorter) / len(longer)
        # 近似匹配
        common = sum(1 for c in shorter if c in longer)
        return common / len(longer)

    def _format_page_range(self, page_numbers: List[int]) -> Optional[str]:
        if not page_numbers:
            return None
        if len(page_numbers) == 1:
            return str(page_numbers[0])
        return f"{min(page_numbers)}-{max(page_numbers)}"


def chunk_document(
    sections: List[ParsedSection],
    metadata: Optional[dict] = None,
    llm: Optional[BaseChatModel] = None,
) -> List[ChunkResult]:
    """分块处理入口（同步包装，供 pipeline 调用）"""
    import asyncio

    chunker = LangChainChunker(llm=llm)
    return asyncio.get_event_loop().run_until_complete(
        chunker.chunk(sections, metadata)
    )
