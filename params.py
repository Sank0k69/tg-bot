"""Pydantic parameter models. Python 3.9: use Optional[X] not X | None."""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class EmptyParams(BaseModel):
    pass


class CreateBotParams(BaseModel):
    name: str = Field(..., description="Bot display name, e.g. 'Репорт Блога'")
    token: str = Field(..., description="Telegram bot token from @BotFather")
    system_prompt: str = Field("", description="AI persona and instructions")
    mode: str = Field("standalone", description="'standalone' or 'webbee'")
    owner_tg_id: str = Field("", description="Your Telegram user ID (optional, alternative to QR linking)")


class BotNameParams(BaseModel):
    bot_name: str = Field(..., description="Bot name to act on")


class BotIdParams(BaseModel):
    bot_id: str = Field(..., description="Bot UUID")


class SetPromptParams(BaseModel):
    bot_name: str = Field(..., description="Bot name")
    system_prompt: str = Field(..., description="New system prompt text")


class AddScheduleParams(BaseModel):
    bot_name: str = Field(..., description="Bot name to add schedule to")
    description: str = Field(..., description="Human-readable description of the schedule")
    cron_expr: str = Field(..., description="Cron expression, e.g. '0 8 * * *' for 8am daily")
    task_type: str = Field(..., description="'analytics_daily' | 'analytics_weekly' | 'custom_message' | 'rss_news_post'")
    message: str = Field("", description="Message text for custom_message task type")
    rss_url: str = Field("", description="RSS feed URL for rss_news_post task type")
    target_chat_id: str = Field("", description="Target Telegram chat ID for group posting (e.g. -1001234567890). Leave empty to post to bot owner.")


class RemoveScheduleParams(BaseModel):
    schedule_id: str = Field(..., description="Schedule UUID to remove")


class SendMessageParams(BaseModel):
    text: str = Field(..., description="Message text to send")
    bot_name: Optional[str] = Field(None, description="Bot name — uses default if not specified")
    chat_id: Optional[str] = Field(None, description="Target chat ID — uses owner_chat_id if not specified")


class TestBotParams(BaseModel):
    bot_name: str = Field(..., description="Bot name to test")
    message: str = Field("Тест! Бот работает.", description="Test message to send")


class SaveSettingsParams(BaseModel):
    default_bot_id: Optional[str] = Field(None, description="Default bot ID for IPC notifications")
