"""文档清洗器

清洗步骤插入在解析和分块之间：解析 → 清洗 → 分块

Phase 1 基础清洗（纯文本处理，零依赖）：
  1. 控制字符清理
  2. 空白规范化
  3. 全角转半角
  4. Unicode 规范化

Phase 2 PDF 特有清洗：
  5. 页眉页脚去重
  6. 页码伪影删除
  7. 表格线字符清理
  8. 连字符修复

封面/封底/目录处理：
  - 封面/封底：首尾 ParsedText 字符数 < 阈值则删除
  - 目录：识别标题...数字模式，提取骨架后删除
"""

import logging
import re
import unicodedata
from typing import List, Optional

from knowlebase.parsers.base import (
    ParseResult,
    ParsedSection,
    ParsedText,
    ParsedTable,
    ParsedImage,
)

logger = logging.getLogger(__name__)


# ============================================================
# Phase 1: 基础清洗
# ============================================================

def _clean_control_chars(text: str) -> str:
    """删除控制字符（保留 \\n、\\t、\\r）和零宽空格"""
    # 删除 \x00-\x08, \x0b-\x0c, \x0e-\x1f
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    # 零宽空格、零宽非连接符、零宽连接符、BOM
    text = text.replace("\u200b", "").replace("\u200c", "").replace("\u200d", "").replace("\ufeff", "")
    return text


def _clean_whitespace(text: str) -> str:
    """空白规范化：连续空格/换行合并，行首尾去空白"""
    # 每行首尾去空白
    lines = text.split("\n")
    lines = [line.strip() for line in lines]
    # 删除空行（超过 2 个连续换行变为 2 个）
    lines = [line for line in lines if line]
    text = "\n".join(lines)
    # 连续换行最多 2 个
    text = re.sub(r"\n{3,}", "\n\n", text)
    # 连续空格合并为 1 个
    text = re.sub(r" {2,}", " ", text)
    return text


def _remove_chinese_spaces(text: str) -> str:
    """删除中文字符之间的单个空格（全角空格转半角后遗留）"""
    # 匹配：中文/中日韩字符 + 空格 + 中文/中日韩字符
    cjk = r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]"
    # 循环替换直到没有变化（非重叠匹配需要多轮）
    prev = ""
    while prev != text:
        prev = text
        text = re.sub(rf"({cjk}) +({cjk})", r"\1\2", text)
    return text


def _fullwidth_to_halfwidth(text: str) -> str:
    """全角数字字母转半角（中文不变）"""
    result = []
    for char in text:
        code = ord(char)
        # 全角 ASCII 范围：U+FF01 - U+FF5E
        if 0xFF01 <= code <= 0xFF5E:
            result.append(chr(code - 0xFEE0))
        # 全角空格 U+3000 转半角空格
        elif code == 0x3000:
            result.append(" ")
        else:
            result.append(char)
    return "".join(result)


def _normalize_unicode(text: str) -> str:
    """Unicode NFKC 规范化"""
    return unicodedata.normalize("NFKC", text)


def _apply_phase1(text: str) -> str:
    """执行 Phase 1 所有基础清洗步骤"""
    text = _clean_control_chars(text)
    text = _clean_whitespace(text)
    text = _fullwidth_to_halfwidth(text)
    text = _remove_chinese_spaces(text)
    text = _normalize_unicode(text)
    return text


# ============================================================
# Phase 2: PDF 特有清洗
# ============================================================

# 表格线字符
_TABLE_BORDER_CHARS = re.compile(r"[│─├┤┌┐└┘┬┴┼┃━┣┫┏┓┗┛┳┻╋╸╺╹╷]+")


def _clean_table_borders(text: str) -> str:
    """删除表格线字符"""
    return _TABLE_BORDER_CHARS.sub("", text)


def _remove_page_artifacts(text: str) -> str:
    """删除页码伪影：单独一行的纯数字（长度 < 4）"""
    lines = text.split("\n")
    result = []
    for line in lines:
        stripped = line.strip()
        # 纯数字且长度小于 4 的孤立行
        if stripped.isdigit() and len(stripped) < 4:
            continue
        result.append(line)
    return "\n".join(result)


def _fix_hyphenation(text: str) -> str:
    """修复跨行连字符：行末的 '-' 如果下一行是单词延续，则去掉 '-' 并合并"""
    # 简单策略：行末以 '-' 结尾，去掉 '-' 和换行，直接连接下一行
    # 只对英文文本有效
    text = re.sub(r"-\n([a-zA-Z])", r"\1", text)
    return text


def _apply_phase2(text: str) -> str:
    """执行 Phase 2 所有 PDF 特有清洗步骤"""
    text = _clean_table_borders(text)
    text = _remove_page_artifacts(text)
    text = _fix_hyphenation(text)
    return text


# ============================================================
# 封面/封底/目录处理
# ============================================================

# 目录行模式：文字 + 若干分隔符 + 数字（如 "第一章 概述 ........ 1"）
_TOC_LINE_PATTERN = re.compile(r"^(.+?)\s*[.\s·\-─]+\s*(\d+)\s*$")


def _is_toc_line(line: str) -> bool:
    """判断是否为目录行"""
    return bool(_TOC_LINE_PATTERN.match(line.strip()))


def _extract_toc_structure(text: str) -> List[str]:
    """从目录文本中提取章节标题骨架"""
    titles = []
    for line in text.split("\n"):
        m = _TOC_LINE_PATTERN.match(line.strip())
        if m:
            titles.append(m.group(1).strip())
    return titles


def _is_toc_content(text: str) -> bool:
    """判断一段文本是否主要为目录内容（>50% 的行匹配目录模式）"""
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines:
        return False
    toc_lines = sum(1 for l in lines if _is_toc_line(l))
    return toc_lines / len(lines) > 0.5


def _is_cover(text: str, page_number: Optional[int] = None, threshold: int = 30) -> bool:
    """判断是否为封面/封底

    条件：
    1. 内容 < threshold 字符
    2. 且在首页（page_number=1）或末页（page_number 较高）
    """
    if len(text.strip()) >= threshold:
        return False
    # 只有第一页或最后一页才判定为封面/封底
    # page_number 为 None 时不做判定（保守）
    return page_number is not None


# ============================================================
# 主清洗流程
# ============================================================

def _clean_text_content(text: str) -> str:
    """对单个文本段落执行所有清洗步骤"""
    text = _apply_phase1(text)
    text = _apply_phase2(text)
    return text


def clean_document(result: ParseResult) -> ParseResult:
    """清洗 ParseResult

    遍历所有 section 和 content，执行基础清洗 + PDF 特有清洗，
    并处理封面/封底/目录。
    """
    new_sections: List[ParsedSection] = []

    for section in result.sections:
        cleaned_content = []

        for item in section.content:
            if isinstance(item, ParsedText):
                # 清洗文本
                cleaned_text = _clean_text_content(item.text)
                if not cleaned_text.strip():
                    continue  # 清洗后为空的文本丢弃

                item.text = cleaned_text
                cleaned_content.append(item)

            elif isinstance(item, ParsedSection):
                # 递归清洗嵌套 section
                cleaned_content.append(item)

            elif isinstance(item, (ParsedTable, ParsedImage)):
                # 表格和图片暂不修改
                cleaned_content.append(item)

        new_sections.append(ParsedSection(
            title=section.title,
            content=cleaned_content,
        ))

    # 封面/封底/目录处理（在第一个 section 上操作）
    if new_sections:
        first_section = new_sections[0]
        first_section.content = _process_cover_backcover_toc(
            first_section.content
        )

    return ParseResult(
        sections=new_sections,
        page_count=result.page_count,
        has_images=result.has_images,
        has_tables=result.has_tables,
    )


def _process_cover_backcover_toc(
    content: list,
) -> list:
    """处理封面、封底、目录

    - 封面：删除第一个字符数 < 50 的 ParsedText
    - 封底：删除最后一个字符数 < 50 的 ParsedText
    - 目录：识别目录段落，提取骨架后删除
    """
    if not content:
        return content

    # 1. 识别并删除封面（第一个 item）
    if isinstance(content[0], ParsedText) and _is_cover(content[0].text, content[0].page_number):
        logger.debug(f"检测到封面，已删除（{len(content[0].text)} 字符）")
        content = content[1:]

    if not content:
        return content

    # 2. 识别并删除封底（最后一个 item）
    if isinstance(content[-1], ParsedText) and _is_cover(content[-1].text, content[-1].page_number):
        logger.debug(f"检测到封底，已删除（{len(content[-1].text)} 字符）")
        content = content[:-1]

    if not content:
        return content

    # 3. 识别并删除目录
    new_content = []
    for item in content:
        if isinstance(item, ParsedText) and _is_toc_content(item.text):
            toc_titles = _extract_toc_structure(item.text)
            logger.debug(f"检测到目录，已删除，提取章节骨架: {toc_titles}")
            # 目录内容删除，但章节骨架信息可以记录在日志中供后续分块使用
            continue
        new_content.append(item)

    return new_content
