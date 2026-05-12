"""IPC send_message endpoint + test_bot chat function + webbee webhook."""
from __future__ import annotations

from imperal_sdk import ActionResult
from imperal_sdk.types import ActionResult  # noqa: F811

from app import chat, ext, load_settings
from params import SendMessageParams, TestBotParams
from api_client import mos_send_message, mos_list_bots


@chat.function(
    "send_message",
    description=(
        "Send a message via a Telegram bot to its owner. "
        "Use when user asks to send a notification or test the bot. "
        "bot_name optional — uses default bot if not specified."
    ),
    action_type="write",
    chain_callable=True,
    effects=["send:message"],
    event="tgbot.message.sent",
)
async def fn_send_message(ctx, params: SendMessageParams) -> ActionResult:
    """Send message via named bot (or default/first active bot)."""
    bot_id = None
    bot_name = params.bot_name

    if not bot_name:
        settings = await load_settings(ctx)
        default_id = settings.get("default_bot_id", "")
        if default_id:
            bot_id = default_id
        else:
            bots = await mos_list_bots(ctx)
            active = [b for b in bots if b.get("enabled") and b.get("owner_chat_id")]
            if not active:
                return ActionResult.error(error="No active linked bots. Create and link one first.")
            bot_id = active[0]["id"]
    else:
        bots = await mos_list_bots(ctx)
        bot = next((b for b in bots if b["name"] == bot_name), None)
        if not bot:
            return ActionResult.error(error=f"Bot '{bot_name}' not found.")
        bot_id = bot["id"]

    result = await mos_send_message(ctx, bot_id=bot_id, chat_id=params.chat_id, text=params.text)
    if "error" in result:
        return ActionResult.error(error=result["error"])
    return ActionResult.success({}, summary="Message sent.")


@ext.expose("send_message")
async def ipc_send_message(ctx, text: str, bot_name: str = None, chat_id: str = None) -> dict:
    """IPC: other extensions call ctx.extensions.call('tg-bot', 'send_message', ...)"""
    params = SendMessageParams(text=text, bot_name=bot_name, chat_id=chat_id)
    result = await fn_send_message(ctx, params)
    return {"ok": result.status == "success", "error": getattr(result, "error", None)}


@chat.function(
    "test_bot",
    description="Send a test message via a bot to verify it is working.",
    action_type="write",
    chain_callable=True,
    effects=["send:message"],
    event="tgbot.message.sent",
)
async def fn_test_bot(ctx, params: TestBotParams) -> ActionResult:
    """Send test message via named bot."""
    result = await mos_send_message(ctx, bot_name=params.bot_name, text=params.message)
    if "error" in result:
        return ActionResult.error(error=result["error"])
    return ActionResult.success({}, summary=f"Test message sent to '{params.bot_name}'.")


@ext.webhook("/tg-message")
async def handle_tg_message(ctx, data: dict) -> dict:
    """Webbee mode: inbound Telegram message with full ctx access. Only responds to owner."""
    if data.get("chat_id") != data.get("owner_chat_id"):
        return {"ok": True}

    text = data.get("text", "")
    bot_id = data.get("bot_id", "")
    chat_id = data.get("chat_id", "")

    if not text or not bot_id or not chat_id:
        return {"ok": True}

    try:
        reply = await ctx.ai.complete(prompt=text, model="claude-haiku-4-5-20251001")
        reply_text = reply.text if hasattr(reply, "text") else str(reply)
    except Exception:
        reply_text = "Could not generate a response."

    await mos_send_message(ctx, bot_id=bot_id, chat_id=chat_id, text=reply_text)
    return {"ok": True}
