"""Tests for schedule and notify handlers."""
import pytest
from unittest.mock import patch, AsyncMock
from imperal_sdk.testing import MockContext

import handlers_schedules
from params import AddScheduleParams, BotNameParams


@pytest.fixture
def ctx():
    return MockContext(role="admin")


@pytest.mark.asyncio
async def test_invalid_task_type_rejected(ctx):
    params = AddScheduleParams(
        bot_name="MyBot", description="Test",
        cron_expr="0 8 * * *", task_type="nonexistent",
    )
    result = await handlers_schedules.fn_add_schedule(ctx, params)
    assert result.status == "error"
    assert "task_type" in result.error.lower() or "invalid" in result.error.lower() or "тип" in result.error.lower()


@pytest.mark.asyncio
async def test_add_schedule_bot_not_found(ctx):
    with patch("handlers_schedules.get_cached_bots", new=AsyncMock(return_value=[])):
        params = AddScheduleParams(
            bot_name="Ghost", description="d",
            cron_expr="0 8 * * *", task_type="custom_message", message="hi",
        )
        result = await handlers_schedules.fn_add_schedule(ctx, params)
    assert result.status == "error"
    assert "not found" in result.error.lower() or "найден" in result.error.lower()


@pytest.mark.asyncio
async def test_add_custom_message_schedule(ctx):
    bots = [{"id": "b1", "name": "MyBot", "enabled": 1}]
    with patch("handlers_schedules.get_cached_bots", new=AsyncMock(return_value=bots)), \
         patch("handlers_schedules.mos_add_schedule", new=AsyncMock(return_value={"id": "s1"})):
        params = AddScheduleParams(
            bot_name="MyBot", description="Daily hello",
            cron_expr="0 8 * * *", task_type="custom_message", message="Good morning!",
        )
        result = await handlers_schedules.fn_add_schedule(ctx, params)
    assert result.status == "success"


@pytest.mark.asyncio
async def test_list_schedules_bot_not_found(ctx):
    with patch("handlers_schedules.get_cached_bots", new=AsyncMock(return_value=[])):
        result = await handlers_schedules.fn_list_schedules(ctx, BotNameParams(bot_name="Ghost"))
    assert result.status == "error"


@pytest.mark.asyncio
async def test_rss_news_post_requires_rss_url(ctx):
    bots = [{"id": "b1", "name": "MyBot", "enabled": 1}]
    with patch("handlers_schedules.get_cached_bots", new=AsyncMock(return_value=bots)):
        params = AddScheduleParams(
            bot_name="MyBot", description="News",
            cron_expr="0 9 * * 1", task_type="rss_news_post",
        )
        result = await handlers_schedules.fn_add_schedule(ctx, params)
    assert result.status == "error"
    assert "rss_url" in result.error.lower()


@pytest.mark.asyncio
async def test_rss_news_post_with_group_chat_id(ctx):
    bots = [{"id": "b1", "name": "MyBot", "enabled": 1}]
    with patch("handlers_schedules.get_cached_bots", new=AsyncMock(return_value=bots)), \
         patch("handlers_schedules.mos_add_schedule", new=AsyncMock(return_value={"id": "s2"})) as mock_add:
        params = AddScheduleParams(
            bot_name="MyBot", description="Weekly news",
            cron_expr="0 9 * * 1", task_type="rss_news_post",
            rss_url="https://example.com/feed.xml",
            target_chat_id="-1001234567890",
        )
        result = await handlers_schedules.fn_add_schedule(ctx, params)
    assert result.status == "success"
    call_kwargs = mock_add.call_args
    assert call_kwargs.kwargs.get("target_chat_id") == "-1001234567890"
