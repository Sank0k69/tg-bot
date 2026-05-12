"""MOS HTTP client — all external calls go through MOS server."""
from __future__ import annotations

SERVER_URL = "https://mos.lexa-lox.xyz"
SERVER_API_KEY = "dd5f08814b30d05ff8b573231a14a6826c39d7c07f226995c9a8b1573ceebb90"
TIMEOUT = 30


def _scope(ctx) -> dict:
    """User isolation scope for MOS requests."""
    return {"user_id": ctx.user.imperal_id, "tenant_id": ctx.user.tenant_id}


async def _post(ctx, endpoint: str, payload: dict, timeout: int = TIMEOUT) -> dict:
    resp = await ctx.http.post(
        f"{SERVER_URL}{endpoint}",
        json=payload,
        headers={"X-API-Key": SERVER_API_KEY},
        timeout=timeout,
    )
    if not resp.ok:
        return {"error": f"Server error {resp.status_code}"}
    return resp.json()


async def mos_create_bot(ctx, name: str, token: str, system_prompt: str,
                          mode: str, owner_tg_id: str) -> dict:
    """Create bot on MOS."""
    return await _post(ctx, "/api/tgbot/create", {
        **_scope(ctx), "name": name, "token": token,
        "system_prompt": system_prompt, "mode": mode, "owner_tg_id": owner_tg_id,
    })


async def mos_list_bots(ctx) -> list:
    """List all bots for this user."""
    data = await _post(ctx, "/api/tgbot/list", _scope(ctx))
    return data.get("bots", [])


async def mos_delete_bot(ctx, bot_id: str) -> dict:
    return await _post(ctx, "/api/tgbot/delete", {**_scope(ctx), "bot_id": bot_id})


async def mos_update_bot(ctx, bot_id: str, **fields) -> dict:
    return await _post(ctx, "/api/tgbot/update", {**_scope(ctx), "bot_id": bot_id, **fields})


async def mos_enable_bot(ctx, bot_id: str) -> dict:
    return await _post(ctx, "/api/tgbot/enable", {**_scope(ctx), "bot_id": bot_id})


async def mos_disable_bot(ctx, bot_id: str) -> dict:
    return await _post(ctx, "/api/tgbot/disable", {**_scope(ctx), "bot_id": bot_id})


async def mos_relink_bot(ctx, bot_id: str) -> dict:
    return await _post(ctx, "/api/tgbot/relink", {**_scope(ctx), "bot_id": bot_id})


async def mos_send_message(ctx, bot_id: str = None, bot_name: str = None,
                            chat_id: str = None, text: str = "") -> dict:
    return await _post(ctx, "/api/tgbot/send", {
        **_scope(ctx), "bot_id": bot_id, "bot_name": bot_name,
        "chat_id": chat_id, "text": text,
    })


async def mos_add_schedule(ctx, bot_id: str, cron_expr: str, description: str,
                            task_type: str, task_config: dict) -> dict:
    return await _post(ctx, "/api/tgbot/schedule/add", {
        **_scope(ctx), "bot_id": bot_id, "cron_expr": cron_expr,
        "description": description, "task_type": task_type, "task_config": task_config,
    })


async def mos_remove_schedule(ctx, schedule_id: str) -> dict:
    return await _post(ctx, "/api/tgbot/schedule/remove", {
        **_scope(ctx), "schedule_id": schedule_id,
    })


async def mos_list_schedules(ctx, bot_id: str) -> list:
    data = await _post(ctx, "/api/tgbot/schedule/list", {**_scope(ctx), "bot_id": bot_id})
    return data.get("schedules", [])
