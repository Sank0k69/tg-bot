"""Bot CRUD chat functions."""
from __future__ import annotations

from imperal_sdk import ActionResult
from imperal_sdk.types import ActionResult  # noqa: F811

from app import chat, load_settings, save_settings, get_cached_bots, invalidate_bots_cache
from params import EmptyParams, CreateBotParams, BotNameParams, SetPromptParams
from api_client import (
    mos_create_bot, mos_list_bots, mos_delete_bot,
    mos_update_bot, mos_enable_bot, mos_disable_bot, mos_relink_bot,
)


def _bot_status(bot: dict) -> str:
    if not bot.get("enabled"):
        return "disabled"
    if not bot.get("owner_chat_id"):
        return "unlinked"
    return "active"


@chat.function(
    "list_bots",
    description="List all Telegram bots for this user.",
    action_type="read",
    event="tgbot.listed",
)
async def fn_list_bots(ctx, params: EmptyParams) -> ActionResult:
    """Show all user bots with status."""
    bots = await get_cached_bots(ctx)
    rows = [
        {"name": b["name"], "mode": b.get("mode", "standalone"),
         "status": _bot_status(b), "id": b["id"]}
        for b in bots
    ]
    summary = (
        f"{len(rows)} bot(s): " + ", ".join(f"{r['name']} ({r['status']})" for r in rows)
        if rows else "No bots yet."
    )
    return ActionResult.success({"bots": rows, "total": len(rows)}, summary=summary)


@chat.function(
    "create_bot",
    description=(
        "Create a new Telegram bot. Requires: name, token from @BotFather, system_prompt. "
        "mode: 'standalone' (custom AI) or 'webbee' (full Imperal access). "
        "owner_tg_id optional — alternative to QR linking."
    ),
    action_type="write",
    chain_callable=True,
    effects=["create:bot"],
    event="tgbot.created",
)
async def fn_create_bot(ctx, params: CreateBotParams) -> ActionResult:
    """Create bot on MOS, register Telegram webhook, return QR + invite link."""
    if not params.token:
        return ActionResult.error(error="Token required — get it from @BotFather in Telegram.")
    result = await mos_create_bot(
        ctx, params.name, params.token, params.system_prompt,
        params.mode, params.owner_tg_id,
    )
    if "error" in result:
        return ActionResult.error(error=result["error"])
    await invalidate_bots_cache(ctx)
    return ActionResult.success(
        result,
        summary=(
            f"Bot '{params.name}' created! @{result.get('bot_username', '')}\n"
            f"Scan QR in panel or open link:\n{result.get('invite_link', '')}\n"
            f"Press START in Telegram to link the bot."
        ),
    )


@chat.function(
    "delete_bot",
    description="Delete a Telegram bot permanently. Removes webhook and all schedules.",
    action_type="destructive",
    chain_callable=True,
    effects=["delete:bot"],
    event="tgbot.deleted",
)
async def fn_delete_bot(ctx, params: BotNameParams) -> ActionResult:
    """Delete bot by name."""
    bots = await get_cached_bots(ctx)
    bot = next((b for b in bots if b["name"] == params.bot_name), None)
    if not bot:
        return ActionResult.error(error=f"Bot '{params.bot_name}' not found.")
    await mos_delete_bot(ctx, bot["id"])
    await invalidate_bots_cache(ctx)
    return ActionResult.success({}, summary=f"Bot '{params.bot_name}' deleted.")


@chat.function(
    "enable_bot",
    description="Enable a disabled Telegram bot.",
    action_type="write",
    chain_callable=True,
    effects=["update:bot"],
    event="tgbot.updated",
)
async def fn_enable_bot(ctx, params: BotNameParams) -> ActionResult:
    """Enable bot by name."""
    bots = await get_cached_bots(ctx)
    bot = next((b for b in bots if b["name"] == params.bot_name), None)
    if not bot:
        return ActionResult.error(error=f"Bot '{params.bot_name}' not found.")
    await mos_enable_bot(ctx, bot["id"])
    await invalidate_bots_cache(ctx)
    return ActionResult.success({}, summary=f"Bot '{params.bot_name}' enabled.")


@chat.function(
    "disable_bot",
    description="Disable a Telegram bot (stops responding to messages).",
    action_type="write",
    chain_callable=True,
    effects=["update:bot"],
    event="tgbot.updated",
)
async def fn_disable_bot(ctx, params: BotNameParams) -> ActionResult:
    """Disable bot by name."""
    bots = await get_cached_bots(ctx)
    bot = next((b for b in bots if b["name"] == params.bot_name), None)
    if not bot:
        return ActionResult.error(error=f"Bot '{params.bot_name}' not found.")
    await mos_disable_bot(ctx, bot["id"])
    await invalidate_bots_cache(ctx)
    return ActionResult.success({}, summary=f"Bot '{params.bot_name}' disabled.")


@chat.function(
    "set_prompt",
    description="Update a bot's system prompt.",
    action_type="write",
    chain_callable=True,
    effects=["update:bot"],
    event="tgbot.updated",
)
async def fn_set_prompt(ctx, params: SetPromptParams) -> ActionResult:
    """Change bot system prompt."""
    bots = await get_cached_bots(ctx)
    bot = next((b for b in bots if b["name"] == params.bot_name), None)
    if not bot:
        return ActionResult.error(error=f"Bot '{params.bot_name}' not found.")
    await mos_update_bot(ctx, bot["id"], system_prompt=params.system_prompt)
    await invalidate_bots_cache(ctx)
    return ActionResult.success({}, summary=f"Prompt updated for '{params.bot_name}'.")


@chat.function(
    "relink_bot",
    description="Re-generate QR code and linking code for a bot (e.g. after changing Telegram account).",
    action_type="write",
    chain_callable=True,
    effects=["update:bot"],
    event="tgbot.updated",
)
async def fn_relink_bot(ctx, params: BotNameParams) -> ActionResult:
    """Generate new link_code, clear owner_chat_id."""
    bots = await get_cached_bots(ctx)
    bot = next((b for b in bots if b["name"] == params.bot_name), None)
    if not bot:
        return ActionResult.error(error=f"Bot '{params.bot_name}' not found.")
    result = await mos_relink_bot(ctx, bot["id"])
    await invalidate_bots_cache(ctx)
    return ActionResult.success(
        result,
        summary=(
            f"New link for '{params.bot_name}':\n"
            f"{result.get('invite_link', '')}\nQR updated in panel."
        ),
    )
