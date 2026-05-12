"""Tests for bot CRUD handlers."""
import pytest
from unittest.mock import patch, AsyncMock
from imperal_sdk.testing import MockContext

import handlers_bots
from params import CreateBotParams, BotNameParams, EmptyParams


@pytest.fixture
def ctx():
    return MockContext(role="admin")


@pytest.mark.asyncio
async def test_list_bots_empty(ctx):
    with patch("handlers_bots.mos_list_bots", new=AsyncMock(return_value=[])):
        result = await handlers_bots.fn_list_bots(ctx, EmptyParams())
    assert result.status == "success"
    assert result.data["total"] == 0
    assert "No bots" in result.summary


@pytest.mark.asyncio
async def test_list_bots_shows_status(ctx):
    bots = [
        {"id": "b1", "name": "MyBot", "enabled": 1, "owner_chat_id": "123", "mode": "standalone"},
        {"id": "b2", "name": "UnlinkedBot", "enabled": 1, "owner_chat_id": None, "mode": "webbee"},
    ]
    with patch("handlers_bots.mos_list_bots", new=AsyncMock(return_value=bots)):
        result = await handlers_bots.fn_list_bots(ctx, EmptyParams())
    assert result.data["total"] == 2
    statuses = {r["name"]: r["status"] for r in result.data["bots"]}
    assert statuses["MyBot"] == "active"
    assert statuses["UnlinkedBot"] == "unlinked"


@pytest.mark.asyncio
async def test_create_bot_requires_token(ctx):
    params = CreateBotParams(name="Bot", token="", system_prompt="Hi", mode="standalone")
    result = await handlers_bots.fn_create_bot(ctx, params)
    assert result.status == "error"
    assert "token" in result.error.lower()


@pytest.mark.asyncio
async def test_delete_bot_not_found(ctx):
    with patch("handlers_bots.mos_list_bots", new=AsyncMock(return_value=[])):
        result = await handlers_bots.fn_delete_bot(ctx, BotNameParams(bot_name="Ghost"))
    assert result.status == "error"
    assert "not found" in result.error.lower()


@pytest.mark.asyncio
async def test_enable_bot_success(ctx):
    bots = [{"id": "b1", "name": "MyBot", "enabled": 0, "owner_chat_id": None}]
    with patch("handlers_bots.mos_list_bots", new=AsyncMock(return_value=bots)), \
         patch("handlers_bots.mos_enable_bot", new=AsyncMock(return_value={"ok": True})):
        result = await handlers_bots.fn_enable_bot(ctx, BotNameParams(bot_name="MyBot"))
    assert result.status == "success"
