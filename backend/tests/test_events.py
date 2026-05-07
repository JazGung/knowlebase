"""
单元测试 - ProcessingEventBus 事件总线
"""

import asyncio
import pytest

from knowlebase.events import ProcessingEventBus, StageCompletedEvent


def make_event(processing_id="proc_test", stage_name="parsed", status="succeeded", duration_ms=100, error_message=None):
    return StageCompletedEvent(
        processing_id=processing_id,
        stage_name=stage_name,
        status=status,
        duration_ms=duration_ms,
        error_message=error_message,
    )


class TestStageCompletedEvent:

    def test_creation(self):
        e = make_event()
        assert e.processing_id == "proc_test"
        assert e.stage_name == "parsed"
        assert e.status == "succeeded"
        assert e.duration_ms == 100
        assert e.error_message is None

    def test_with_error(self):
        e = make_event(status="failed", error_message="解析失败")
        assert e.status == "failed"
        assert e.error_message == "解析失败"

    def test_to_json(self):
        e = make_event()
        json_str = e.to_json()
        assert "proc_test" in json_str
        assert "parsed" in json_str


class TestProcessingEventBus:

    @pytest.fixture
    def bus(self):
        return ProcessingEventBus()

    @pytest.mark.asyncio
    async def test_publish_no_subscribers_does_not_crash(self, bus):
        await bus.publish(make_event())

    @pytest.mark.asyncio
    async def test_subscriber_receives_event(self, bus):
        event = make_event()

        async def consume():
            results = []
            async for e in bus.subscribe():
                results.append(e)
                if len(results) >= 1:
                    break
            return results

        task = asyncio.create_task(consume())
        await asyncio.sleep(0.01)  # let subscriber register
        await bus.publish(event)
        results = await asyncio.wait_for(task, timeout=1.0)

        assert len(results) == 1
        assert results[0].processing_id == "proc_test"

    @pytest.mark.asyncio
    async def test_subscriber_filtered_by_processing_id(self, bus):
        event_a = make_event(processing_id="proc_a")
        event_b = make_event(processing_id="proc_b")

        async def consume():
            results = []
            async for e in bus.subscribe(processing_id="proc_b"):
                results.append(e)
                if len(results) >= 1:
                    break
            return results

        task = asyncio.create_task(consume())
        await asyncio.sleep(0.01)
        await bus.publish(event_a)  # should be filtered out
        await bus.publish(event_b)  # should be received
        results = await asyncio.wait_for(task, timeout=1.0)

        assert len(results) == 1
        assert results[0].processing_id == "proc_b"

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self, bus):
        event = make_event()

        async def consume():
            results = []
            async for e in bus.subscribe():
                results.append(e)
                if len(results) >= 1:
                    break
            return results

        t1 = asyncio.create_task(consume())
        t2 = asyncio.create_task(consume())
        await asyncio.sleep(0.01)
        await bus.publish(event)
        r1 = await asyncio.wait_for(t1, timeout=1.0)
        r2 = await asyncio.wait_for(t2, timeout=1.0)

        assert len(r1) == 1
        assert len(r2) == 1

    @pytest.mark.asyncio
    async def test_subscriber_count(self, bus):
        assert bus.subscriber_count == 0

        async def consume():
            async for _ in bus.subscribe():
                pass

        task = asyncio.create_task(consume())
        await asyncio.sleep(0.01)
        assert bus.subscriber_count == 1

        task.cancel()
        # subscribe() catches CancelledError internally, task exits cleanly
        await task
        await asyncio.sleep(0.01)
        assert bus.subscriber_count == 0
