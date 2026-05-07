"""
ProcessingEventBus - 处理流水线事件总线

基于 asyncio.Queue 的事件分发实现。处理流水线各阶段完成后发布 StageCompletedEvent，
SSE 模块通过 subscribe() 注册监听器消费事件。
"""

import asyncio
import json
import logging
from dataclasses import dataclass, asdict
from typing import AsyncIterator, Set

logger = logging.getLogger(__name__)


@dataclass
class StageCompletedEvent:
    """阶段完成事件消息体"""
    processing_id: str
    stage_name: str
    status: str  # running/succeeded/failed
    duration_ms: int
    error_message: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


class ProcessingEventBus:
    """处理流水线事件总线

    使用 asyncio.Queue 作为事件队列，支持多订阅者。
    生产者（处理模块）调用 publish() 发布事件，不感知消费者。
    消费者（SSE 模块）调用 subscribe() 获取异步迭代器。
    """

    def __init__(self):
        self._queue: asyncio.Queue[StageCompletedEvent] = asyncio.Queue()
        self._subscribers: Set[asyncio.Queue[StageCompletedEvent]] = set()

    async def publish(self, event: StageCompletedEvent) -> None:
        """发布事件到所有订阅者"""
        logger.debug(
            f"事件发布: processing_id={event.processing_id}, "
            f"stage={event.stage_name}, status={event.status}"
        )
        # 写入全局队列（供新订阅者回放）
        await self._queue.put(event)
        # 广播到所有活跃订阅者
        dead: list[asyncio.Queue[StageCompletedEvent]] = []
        for sub_queue in self._subscribers:
            try:
                sub_queue.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(sub_queue)
        for q in dead:
            self._subscribers.discard(q)

    async def subscribe(
        self, processing_id: str | None = None
    ) -> AsyncIterator[StageCompletedEvent]:
        """订阅事件，返回异步迭代器

        Args:
            processing_id: 可选，过滤特定处理任务的事件。None 则接收所有事件。

        Yields:
            StageCompletedEvent 实例
        """
        sub_queue: asyncio.Queue[StageCompletedEvent] = asyncio.Queue(maxsize=256)
        self._subscribers.add(sub_queue)
        try:
            while True:
                event = await sub_queue.get()
                if processing_id is None or event.processing_id == processing_id:
                    yield event
        except asyncio.CancelledError:
            pass
        finally:
            self._subscribers.discard(sub_queue)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


# 模块级单例
_event_bus: ProcessingEventBus | None = None


def get_event_bus() -> ProcessingEventBus:
    """获取 ProcessingEventBus 单例"""
    global _event_bus
    if _event_bus is None:
        _event_bus = ProcessingEventBus()
    return _event_bus
