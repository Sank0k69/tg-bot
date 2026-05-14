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


@ext.webhook("tg-message")
async def handle_tg_message(ctx, headers: dict, body: str, query_params: dict) -> dict:
    """Webbee mode: receive TG message — store + emit event for on_event handler."""
    import json as _json
    import os as _os
    import uuid as _uuid

    # Verify shared secret
    expected = _os.environ.get("WEBBEE_WEBHOOK_SECRET", "imperal-tgbot-secret")
    incoming = headers.get("X-Webbee-Secret") or headers.get("x-webbee-secret") or ""
    if incoming != expected:
        return {"ok": False, "error": "unauthorized"}

    try:
        data = _json.loads(body) if isinstance(body, str) else body
    except Exception:
        return {"ok": True}

    chat_id = data.get("chat_id", "")
    text = data.get("text", "")
    bot_id = data.get("bot_id", "")
    token = data.get("token", "")

    if not chat_id or not text or not bot_id:
        return {"ok": True}

    # Store pending message — on_event handler will pick it up with full ctx
    msg_id = str(_uuid.uuid4())
    try:
        await ctx.store.create("tg_pending", {
            "id": msg_id,
            "chat_id": chat_id,
            "text": text,
            "bot_id": bot_id,
            "token": token,
            "user_id": data.get("user_id", ""),
            "tenant_id": data.get("tenant_id", ""),
        })
    except Exception:
        pass

    # Emit event → on_event handler runs with full ctx.ai + ctx.extensions
    try:
        await ctx.extensions.emit("tg.message.received", {
            "msg_id": msg_id,
            "chat_id": chat_id,
            "text": text,
            "token": token,
            "bot_id": bot_id,
        })
    except Exception:
        # Fallback: direct AI call via MOS if event system unavailable
        try:
            resp = await ctx.http.post(
                f"{SERVER_URL}/api/tgbot/ai-chat",
                json={"message": text, "history": [], "system_prompt": "Ты личный ассистент. Отвечай кратко по-русски без markdown."},
                headers={"X-API-Key": SERVER_API_KEY},
                timeout=20,
            )
            reply_text = resp.json().get("reply", "Не удалось сформировать ответ.") if resp.ok else "Ошибка."
            import httpx as _httpx
            async with _httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={"chat_id": chat_id, "text": reply_text},
                )
        except Exception:
            pass

    return {"ok": True}


@ext.on_event("tg.message.received")
async def process_tg_message(ctx, event_data: dict):
    """Full Webbee context — ctx.ai + ctx.extensions.call available here."""
    import httpx as _httpx

    chat_id = event_data.get("chat_id", "")
    text = event_data.get("text", "")
    token = event_data.get("token", "")

    if not chat_id or not text or not token:
        return

    reply_text = "Не удалось сформировать ответ."

    try:
        # Try IPC with SE Ranking via wp-blogger extension
        rankings_context = ""
        try:
            rankings = await ctx.extensions.call("wp-blogger", "fetch_rankings")
            if rankings and not getattr(rankings, "error", None):
                data = getattr(rankings, "data", {}) or {}
                if data.get("rankings"):
                    top = data["rankings"][:5]
                    rankings_context = "Текущие позиции в Google: " + ", ".join(
                        f"{r.get('keyword')} — #{r.get('position', '?')}" for r in top
                    )
        except Exception:
            pass

        # Try IPC with analytics
        analytics_context = ""
        try:
            analytics = await ctx.extensions.call("analytics", "get_daily_stats")
            if analytics and not getattr(analytics, "error", None):
                data = getattr(analytics, "data", {}) or {}
                if data.get("visits"):
                    analytics_context = f"Трафик вчера: {data['visits']} визитов, {data.get('pageviews', 0)} просмотров."
        except Exception:
            pass

        # Build context-enriched prompt
        context_block = "\n".join(filter(None, [rankings_context, analytics_context]))
        system = (
            "Ты личный бизнес-ассистент Александра, WebHostMost. "
            "Отвечай кратко по-русски без markdown. "
            "Используй эмодзи для структуры. "
            + (f"\n\nАктуальные данные:\n{context_block}" if context_block else "")
        )

        # Use ctx.ai (available in on_event!)
        result = await ctx.ai.complete(
            prompt=text,
            model="claude-haiku-4-5-20251001",
            system=system,
        )
        reply_text = result.text if hasattr(result, "text") else str(result)

    except Exception as e:
        print(f"[on_event] processing error: {e}")
        # Fallback to MOS
        try:
            resp = await ctx.http.post(
                f"{SERVER_URL}/api/tgbot/ai-chat",
                json={"message": text, "history": [], "system_prompt": "Ты личный ассистент. Отвечай кратко по-русски без markdown."},
                headers={"X-API-Key": SERVER_API_KEY},
                timeout=20,
            )
            if resp.ok:
                reply_text = resp.json().get("reply", reply_text)
        except Exception:
            pass

    # Send to Telegram
    try:
        async with _httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": reply_text},
            )
    except Exception as e:
        print(f"[on_event] TG send failed: {e}")
