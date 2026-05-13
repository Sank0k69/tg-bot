"""IPC send_message endpoint + test_bot chat function + webbee webhook."""
from __future__ import annotations

from imperal_sdk import ActionResult
from imperal_sdk.types import ActionResult  # noqa: F811

from app import chat, ext, load_settings
from params import SendMessageParams, TestBotParams
from tgbot_api import mos_send_message, mos_list_bots, SERVER_URL, SERVER_API_KEY


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
    result = await mos_send_message(ctx, bot_name=params.bot_name, text=params.message)
    if "error" in result:
        return ActionResult.error(error=result["error"])
    return ActionResult.success({}, summary=f"Test message sent to '{params.bot_name}'.")


@ext.webhook("/tg-message")
async def handle_tg_message(ctx, headers: dict, body: str, query_params: dict) -> dict:
    """Webbee mode: receive TG message from MOS, process with AI, send reply."""
    import json as _json
    import os as _os

    # Verify shared secret from MOS
    expected = _os.environ.get("WEBBEE_WEBHOOK_SECRET", "imperal-tgbot-secret")
    if headers.get("X-Webbee-Secret", "") != expected:
        return {"ok": False, "error": "unauthorized"}

    try:
        data = _json.loads(body) if isinstance(body, str) else body
    except Exception:
        return {"ok": True}

    chat_id = data.get("chat_id", "")
    text = data.get("text", "")
    bot_id = data.get("bot_id", "")
    token = data.get("token", "")  # decrypted token passed from MOS

    if not chat_id or not text or not bot_id:
        return {"ok": True}

    # Generate short AI reply via MOS dedicated chat endpoint
    reply_text = "Не удалось сформировать ответ."
    try:
        resp = await ctx.http.post(
            f"{SERVER_URL}/api/tgbot/ai-chat",
            json={
                "message": text,
                "history": [],
                "system_prompt": (
                    "Ты личный ассистент Александра. "
                    "Отвечай кратко (1-3 предложения), по-русски, по делу. "
                    "Это Telegram — не пиши длинные статьи."
                ),
            },
            headers={"X-API-Key": SERVER_API_KEY},
            timeout=20,
        )
        if resp.ok:
            reply_text = resp.json().get("reply", reply_text)
    except Exception as e:
        print(f"[webbee-webhook] AI call failed: {e}")

    # Send reply via Telegram directly (token available from payload)
    if token:
        try:
            import httpx as _httpx
            async with _httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={"chat_id": chat_id, "text": reply_text, "parse_mode": "HTML"},
                )
        except Exception as e:
            print(f"[webbee-webhook] TG send failed: {e}")

    return {"ok": True}
