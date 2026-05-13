"""TG Bot Builder — extension core init and settings helpers."""
from __future__ import annotations

from imperal_sdk import Extension, ChatExtension

ext = Extension(
    "tg-bot",
    version="1.0.0",
    display_name="TG Bot Builder",
    description=(
        "Create and manage Telegram bots connected to Imperal. "
        "Build notification bots, AI assistants, and automated report delivery via Telegram."
    ),
    icon="icon.svg",
)

chat = ChatExtension(
    ext,
    tool_name="tg_bot",
    description=(
        "TG Bot Builder — create Telegram bots. "
        "ALWAYS use for: создать бота, настрой бота, добавь расписание уведомлений, "
        "отправь сообщение через бота, покажи ботов, удали бота, "
        "настрой уведомления в Telegram, привяжи бота, перепривяжи бота."
    ),
    max_rounds=10,
)

SETTINGS_COL = "tgbot_settings"
DEFAULT_SETTINGS: dict = {"default_bot_id": ""}


async def load_settings(ctx) -> dict:
    try:
        page = await ctx.store.query(SETTINGS_COL, limit=1)
        docs = getattr(page, "data", None) or []
        if docs and isinstance(getattr(docs[0], "data", None), dict):
            return {**DEFAULT_SETTINGS, **docs[0].data}
    except Exception:
        pass
    return dict(DEFAULT_SETTINGS)


async def save_settings(ctx, values: dict) -> dict:
    current = await load_settings(ctx)
    merged = {**current, **{k: v for k, v in values.items() if v is not None}}
    page = await ctx.store.query(SETTINGS_COL, limit=1)
    docs = getattr(page, "data", None) or []
    if docs:
        await ctx.store.update(SETTINGS_COL, docs[0].id, merged)
    else:
        await ctx.store.create(SETTINGS_COL, merged)
    return merged


BOTS_CACHE_KEY = "tgbot_bots_list"
BOTS_CACHE_TTL = 60


async def get_cached_bots(ctx) -> list:
    try:
        cached = await ctx.cache.get(BOTS_CACHE_KEY)
        if cached is not None:
            return cached
    except Exception:
        pass
    from tgbot_api import mos_list_bots
    try:
        bots = await mos_list_bots(ctx)
    except Exception:
        bots = []
    try:
        await ctx.cache.set(BOTS_CACHE_KEY, bots, ttl=BOTS_CACHE_TTL)
    except Exception:
        pass
    return bots


async def invalidate_bots_cache(ctx) -> None:
    try:
        await ctx.cache.set(BOTS_CACHE_KEY, None, ttl=1)
    except Exception:
        pass


async def _gw_post(message: str = "", ctx=None, **kwargs) -> dict:
    if ctx is not None:
        return await chat._handle(ctx, message, **kwargs)
    return {"status": "ok", "response": ""}


@ext.health_check
async def health_check(ctx):
    settings = await load_settings(ctx)
    if not settings.get("default_bot_id"):
        return {"status": "degraded", "reason": "No default bot set. Create a bot to get started."}
    return {"status": "ok"}
