"""Bot CRUD chat functions."""
from __future__ import annotations

from imperal_sdk import ActionResult
from imperal_sdk.types import ActionResult  # noqa: F811

from app import chat, load_settings, save_settings, get_cached_bots, invalidate_bots_cache
from params import EmptyParams, CreateBotParams, BotNameParams, BotIdParams, SetPromptParams
from api_client import (
    mos_create_bot, mos_list_bots, mos_delete_bot,
    mos_update_bot, mos_enable_bot, mos_disable_bot, mos_relink_bot,
)

NAV_COLLECTION = "tgbot_nav"


async def _set_nav(ctx, view: str) -> None:
    page = await ctx.store.query(NAV_COLLECTION, limit=1)
    docs = getattr(page, "data", None) or []
    if docs:
        await ctx.store.update(NAV_COLLECTION, docs[0].id, {"view": view})
    else:
        await ctx.store.create(NAV_COLLECTION, {"view": view})


def _bot_status(bot: dict) -> str:
    if not bot.get("enabled"):
        return "disabled"
    if not bot.get("owner_chat_id"):
        return "unlinked"
    return "active"


@chat.function(
    "show_create_form",
    description="Navigate to bot creation wizard step 1 (BotFather instructions).",
    action_type="read",
    event="tgbot.nav_create",
)
async def fn_show_create_form(ctx, params: EmptyParams) -> ActionResult:
    await _set_nav(ctx, "create")
    return ActionResult.success({}, summary="")


@chat.function(
    "show_step2_form",
    description="Navigate to bot creation wizard step 2 (token input form).",
    action_type="read",
    event="tgbot.nav_step2",
)
async def fn_show_step2_form(ctx, params: EmptyParams) -> ActionResult:
    await _set_nav(ctx, "step2")
    return ActionResult.success({}, summary="")


@chat.function(
    "open_bot_detail",
    description="Open a specific bot's detail view in the panel.",
    action_type="read",
    event="tgbot.nav_detail",
)
async def fn_open_bot_detail(ctx, params: BotIdParams) -> ActionResult:
    await _set_nav(ctx, f"detail:{params.bot_id}")
    return ActionResult.success({}, summary="")


@chat.function(
    "list_bots",
    description="List all Telegram bots for this user.",
    action_type="read",
    event="tgbot.listed",
)
async def fn_list_bots(ctx, params: EmptyParams) -> ActionResult:
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
        "Create a new Telegram bot. Requires: name, token from @BotFather. "
        "mode defaults to standalone. owner_tg_id optional."
    ),
    action_type="write",
    chain_callable=True,
    effects=["create:bot"],
    event="tgbot.created",
)
async def fn_create_bot(ctx, params: CreateBotParams) -> ActionResult:
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
            f"Scan QR in panel or open: {result.get('invite_link', '')}\n"
            f"Press START in Telegram to link."
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
    bots = await get_cached_bots(ctx)
    bot = next((b for b in bots if b["name"] == params.bot_name), None)
    if not bot:
        return ActionResult.error(error=f"Bot '{params.bot_name}' not found.")
    await mos_update_bot(ctx, bot["id"], system_prompt=params.system_prompt)
    await invalidate_bots_cache(ctx)
    return ActionResult.success({}, summary=f"Prompt updated for '{params.bot_name}'.")


@chat.function(
    "relink_bot",
    description="Re-generate QR code and linking code for a bot.",
    action_type="write",
    chain_callable=True,
    effects=["update:bot"],
    event="tgbot.updated",
)
async def fn_relink_bot(ctx, params: BotNameParams) -> ActionResult:
    bots = await get_cached_bots(ctx)
    bot = next((b for b in bots if b["name"] == params.bot_name), None)
    if not bot:
        return ActionResult.error(error=f"Bot '{params.bot_name}' not found.")
    result = await mos_relink_bot(ctx, bot["id"])
    await invalidate_bots_cache(ctx)
    return ActionResult.success(
        result,
        summary=f"New link for '{params.bot_name}':\n{result.get('invite_link', '')}\nQR updated.",
    )
