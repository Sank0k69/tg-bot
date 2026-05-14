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
    with patch("handlers_schedules.mos_list_bots", new=AsyncMock(return_value=[])):
        params = AddScheduleParams(
            bot_name="Ghost", description="d",
            cron_expr="0 8 * * *", task_type="custom_message", message="hi",
        )
        result = await handlers_schedules.fn_add_schedule(ctx, params)
    assert result.status == "error"
    assert "not found" in result.error.lower()


@pytest.mark.asyncio
async def test_add_custom_message_schedule(ctx):
    bots = [{"id": "b1", "name": "MyBot", "enabled": 1}]
    with patch("handlers_schedules.mos_list_bots", new=AsyncMock(return_value=bots)), \
         patch("handlers_schedules.mos_add_schedule", new=AsyncMock(return_value={"id": "s1"})):
        params = AddScheduleParams(
            bot_name="MyBot", description="Daily hello",
            cron_expr="0 8 * * *", task_type="custom_message", message="Good morning!",
        )
        result = await handlers_schedules.fn_add_schedule(ctx, params)
    assert result.status == "success"


@pytest.mark.asyncio
async def test_list_schedules_bot_not_found(ctx):
    with patch("handlers_schedules.mos_list_bots", new=AsyncMock(return_value=[])):
        result = await handlers_schedules.fn_list_schedules(ctx, BotNameParams(bot_name="Ghost"))
    assert result.status == "error"
