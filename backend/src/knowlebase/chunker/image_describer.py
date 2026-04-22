"""图片描述生成

从 MinIO 下载图片，调用视觉模型生成描述文字。
"""

import logging
from typing import Optional

from knowlebase.core.config import settings
from knowlebase.parsers.image_storage import get_image

logger = logging.getLogger(__name__)

IMAGE_MARKER_START = "[IMAGE_START:{caption}]"
IMAGE_MARKER_END = "[IMAGE_END]"


def describe_image(image_path: str, caption: str = "") -> str:
    """调用视觉模型生成图片描述

    Args:
        image_path: MinIO 对象路径
        caption: 原始 caption（如页码位置）

    Returns:
        图片描述文字
    """
    try:
        from openai import OpenAI
    except ImportError:
        logger.error("openai 未安装，请运行: pip install openai")
        raise

    img_bytes = get_image(image_path)
    if not img_bytes:
        logger.warning(f"无法下载图片: {image_path}")
        return caption or "[图片]"

    import base64
    img_base64 = base64.b64encode(img_bytes).decode("utf-8")

    cfg = settings.get_image_describer_llm_config()

    client = OpenAI(
        api_key=cfg["api_key"],
        base_url=cfg["api_base"],
    )

    prompt = "请用简洁的中文描述这张图片的内容。如果是图表、流程图或表格，请说明其结构和关键信息。50字以内。"

    try:
        response = client.chat.completions.create(
            model=cfg["model"],
            messages=[
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/png;base64,{img_base64}"
                    }}
                ]}
            ],
            max_tokens=200,
        )
        description = response.choices[0].message.content or ""
        logger.debug(f"图片描述生成: {description[:50]}...")
        return description
    except Exception as e:
        logger.error(f"图片描述生成失败: {e}")
        return caption or "[图片]"


def replace_images_with_markers(sections: list) -> list:
    """将 ParseResult 中的 ParsedImage 替换为带标记的描述文本

    Args:
        sections: ParseResult.sections

    Returns:
        修改后的 sections 列表（原地修改）
    """
    from knowlebase.parsers.base import ParsedImage, ParsedText

    for section in sections:
        new_content = []
        for item in section.content:
            if isinstance(item, ParsedImage):
                # 生成描述
                description = describe_image(item.image_path, item.caption)
                # 用带标记的描述文本替换
                marker_text = f"{IMAGE_MARKER_START.format(caption=item.caption)}{description}{IMAGE_MARKER_END}"
                new_content.append(
                    ParsedText(
                        text=marker_text,
                        page_number=item.page_number,
                    )
                )
                logger.debug(f"图片替换: {item.caption} -> {description[:30]}...")
            else:
                new_content.append(item)
        section.content = new_content

    return sections
