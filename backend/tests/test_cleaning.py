"""
文档清洗模块单元测试

运行方式: pytest backend/tests/test_cleaning.py -v
"""

import logging

logger = logging.getLogger(__name__)

import pytest

from knowlebase.parsers.base import ParseResult, ParsedSection, ParsedText, ParsedTable
from knowlebase.cleaners import clean_document


# ============================================================
# Phase 1: 基础清洗
# ============================================================

@pytest.mark.asyncio
async def test_clean_control_chars():
    """控制字符清理"""
    text = "Hello\x00World\x08\x0b\x0c\x0e\x1fTest"
    result = _clean_only(text)
    assert "\x00" not in result
    assert "\x08" not in result
    assert "HelloWorldTest" in result


@pytest.mark.asyncio
async def test_clean_zero_width_chars():
    """零宽字符清理"""
    text = "Hello\u200bWorld\u200cTest\u200dEnd\uFEFF"
    result = _clean_only(text)
    assert "\u200b" not in result
    assert "\u200c" not in result
    assert "\u200d" not in result
    assert "\ufeff" not in result
    assert "HelloWorldTestEnd" in result


@pytest.mark.asyncio
async def test_clean_whitespace():
    """空白规范化"""
    text = "  hello   world  \n\n\n   \nfoo"
    result = _clean_only(text)
    assert "  hello" not in result  # 行首空白应去除
    assert "hello   world" not in result  # 连续空格应合并
    assert "\n\n\n" not in result  # 连续换行应缩减


@pytest.mark.asyncio
async def test_fullwidth_to_halfwidth():
    """全角转半角"""
    text = "ＡＢＣ１２３中文"
    result = _clean_only(text)
    assert "ABC" in result
    assert "123" in result
    assert "中文" in result  # 中文不变


@pytest.mark.asyncio
async def test_unicode_normalization():
    """Unicode NFKC 规范化：罗马数字会被规范化为字母形式"""
    text = "\u2160\u2161\u2162"  # Ⅰ Ⅱ Ⅲ
    result = _clean_only(text)
    # NFKC 将 ⅠⅡⅢ 规范化为 IIIIII
    assert "III" in result
    assert len(result) >= len(text)  # 规范化后字符数可能增加


@pytest.mark.asyncio
async def test_chinese_spaces_removed():
    """中文字符间空格被删除"""
    # 全角空格转半角后遗留的空格
    text = "正\u3000\u3000文\u3000\u3000内\u3000\u3000容"
    result = _clean_only(text)
    assert result == "正文内容"


# ============================================================
# Phase 2: PDF 特有清洗
# ============================================================

@pytest.mark.asyncio
async def test_clean_table_borders():
    """表格线字符清理"""
    text = "│ 姓名 │ 年龄 │\n├──────┼──────┤\n│ 张三 │  25  │"
    result = _clean_only(text)
    assert "│" not in result
    assert "├" not in result
    assert "─" not in result
    assert "姓名" in result
    assert "年龄" in result


@pytest.mark.asyncio
async def test_remove_page_artifacts():
    """页码伪影删除"""
    text = "这是正文内容\n\n3\n\n继续正文"
    result = _clean_only(text)
    # 孤立数字 3 应被删除
    assert "\n3\n" not in result
    assert "正文内容" in result


@pytest.mark.asyncio
async def test_fix_hyphenation():
    """跨行连字符修复"""
    text = "This is an exam-\nple of hyphenation"
    result = _clean_only(text)
    assert "example" in result


# ============================================================
# 封面/封底/目录处理
# ============================================================

@pytest.mark.asyncio
async def test_cover_removal():
    """封面删除"""
    cover_text = "Company Name"  # < 30 chars, page 1
    body_text = "This is the actual document content with meaningful information about the subject matter and it is long enough."

    result = ParseResult(sections=[
        ParsedSection(title="", content=[
            ParsedText(text=cover_text, page_number=1),
            ParsedText(text=body_text, page_number=2),
        ])
    ])

    cleaned = clean_document(result)
    texts = [c for c in cleaned.sections[0].content if isinstance(c, ParsedText)]
    assert len(texts) == 1
    assert texts[0].text == body_text


@pytest.mark.asyncio
async def test_backcover_removal():
    """封底删除"""
    body_text = "This is the actual document content with meaningful information."
    backcover_text = "Thank you"  # < 30 chars, last page

    result = ParseResult(sections=[
        ParsedSection(title="", content=[
            ParsedText(text=body_text, page_number=1),
            ParsedText(text=backcover_text, page_number=5),
        ])
    ])

    cleaned = clean_document(result)
    texts = [c for c in cleaned.sections[0].content if isinstance(c, ParsedText)]
    assert len(texts) == 1
    assert texts[0].text == body_text


@pytest.mark.asyncio
async def test_short_content_not_deleted():
    """短内容但不在封面/封底位置，不应删除"""
    text = "这是第一章的正文内容。"  # 11 chars, but page_number=1 so is_cover returns True

    result = ParseResult(sections=[
        ParsedSection(title="", content=[
            ParsedText(text=text, page_number=1),
        ])
    ])

    cleaned = clean_document(result)
    texts = [c for c in cleaned.sections[0].content if isinstance(c, ParsedText)]
    # page 1 + < 30 chars = cover, so deleted
    assert len(texts) == 0


@pytest.mark.asyncio
async def test_toc_removal():
    """目录识别和删除"""
    toc_text = "第一章 概述 ........ 1\n第二章 需求 ........ 5\n第三章 设计 ........ 12"
    body_text = "This is the actual document content with meaningful information about the subject matter."

    result = ParseResult(sections=[
        ParsedSection(title="", content=[
            ParsedText(text=toc_text, page_number=1),
            ParsedText(text=body_text, page_number=2),
        ])
    ])

    cleaned = clean_document(result)
    texts = [c for c in cleaned.sections[0].content if isinstance(c, ParsedText)]
    # TOC 和封面都应该删除，只剩正文
    assert len(texts) == 1
    assert "subject matter" in texts[0].text


@pytest.mark.asyncio
async def test_non_toc_preserved():
    """非目录内容保留"""
    body_text = "This document contains section one about basic knowledge and section two about advanced topics."

    result = ParseResult(sections=[
        ParsedSection(title="", content=[
            ParsedText(text=body_text, page_number=1),
        ])
    ])

    cleaned = clean_document(result)
    texts = [c for c in cleaned.sections[0].content if isinstance(c, ParsedText)]
    assert len(texts) == 1
    assert "basic knowledge" in texts[0].text


# ============================================================
# 集成测试
# ============================================================

@pytest.mark.asyncio
async def test_full_pipeline():
    """完整清洗流水线"""
    result = ParseResult(sections=[
        ParsedSection(title="", content=[
            ParsedText(text="封面", page_number=1),  # 封面
            ParsedText(text="第一章 概述 ........ 1\n第二章 详情 ........ 5", page_number=2),  # 目录
            ParsedText(text="正\u3000\u3000文\u3000\u3000内\u3000\u3000容，这\u3000\u3000里\u3000\u3000有\u3000\u3000多\u3000\u3000余\u3000\u3000空\u3000\u3000格", page_number=3),
            ParsedText(text="│ 数据 │\n│ 100  │", page_number=4),  # 表格线
            ParsedText(text="封底", page_number=10),  # 封底
        ])
    ])

    cleaned = clean_document(result)
    texts = cleaned.sections[0].content

    # 封面和封底应删除
    text_values = [t.text for t in texts if isinstance(t, ParsedText)]
    assert "封面" not in text_values
    assert "封底" not in text_values

    # 目录应删除
    assert not any("概述" in t.text for t in texts if isinstance(t, ParsedText))

    # 正文应被清洗（控制字符删除、全角空格去除、全角标点转半角）
    body = [t for t in texts if isinstance(t, ParsedText) and "正文内容" in t.text]
    assert len(body) == 1
    assert "\u3000" not in body[0].text
    assert "正文内容,这里有多余空格" in body[0].text  # 全角逗号，转半角

    # 表格线应清理
    table_line = [t for t in texts if isinstance(t, ParsedText) and "数据" in t.text]
    assert len(table_line) == 1
    assert "│" not in table_line[0].text


# ============================================================
# 辅助函数
# ============================================================

def _clean_only(text: str) -> str:
    """只清洗文本（不经过 ParseResult 包装）"""
    from knowlebase.cleaners import _clean_text_content
    return _clean_text_content(text)
