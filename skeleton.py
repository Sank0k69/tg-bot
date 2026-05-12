"""Skeleton context — inject bot status into Webbee LLM context."""
from __future__ import annotations

from app import ext, load_settings, get_cached_bots


@ext.skeleton(
    "tgbot_status",
    ttl=60,
    description="User Telegram bots — names, active status, link status",
)
async def refresh_tgbot_status(ctx) -> dict:
    """Inject bot state so Webbee knows what bots exist and their status."""
    try:
        bots = await get_cached_bots(ctx)
    except Exception:
        bots = []

    active   = [b["name"] for b in bots if b.get("enabled") and b.get("owner_chat_id")]
    unlinked = [b["name"] for b in bots if not b.get("owner_chat_id")]
    settings = await load_settings(ctx)

    return {"response": {
        "total_bots":    len(bots),
        "active_bots":   active,
        "unlinked_bots": unlinked,
        "default_bot_id": settings.get("default_bot_id", ""),
        "instruction": (
            f"{len(active)} active bot(s): {', '.join(active) or 'none'}. "
            + (f"Unlinked (need /start): {', '.join(unlinked)}. " if unlinked else "")
            + "Use send_message to send notifications. Use create_bot to add a new one."
        ),
    }}
