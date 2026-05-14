"""Schedule management chat functions."""
from __future__ import annotations

from imperal_sdk import ActionResult
from imperal_sdk.types import ActionResult  # noqa: F811

from app import chat, load_settings, get_cached_bots, get_current_bot_name
from params import AddScheduleParams, RemoveScheduleParams, BotNameParams
from tgbot_api import mos_list_bots, mos_add_schedule, mos_remove_schedule, mos_list_schedules

VALID_TASK_TYPES = ("analytics_daily", "analytics_weekly", "custom_message")


def _parse_cron_natural(text: str) -> str:
    """Convert natural language to cron. Returns cron string or original if already valid."""
    import re
    t = text.lower().strip()

    # Already valid cron (5 fields)
    if re.match(r'^[\d\*\/\-\,]+ [\d\*\/\-\,]+ [\d\*\/\-\,]+ [\d\*\/\-\,]+ [\d\*\/\-\,]+$', t):
        return t

    # Extract hour
    hour_match = re.search(r'в\s+(\d{1,2})', t) or re.search(r'at\s+(\d{1,2})', t)
    hour = hour_match.group(1) if hour_match else "8"

    # Daily patterns
    if any(w in t for w in ["каждый день", "ежедневно", "каждое утро", "каждый вечер", "каждую ночь", "daily", "every day"]):
        if "вечер" in t:
            hour = hour_match.group(1) if hour_match else "19"
        elif "ночь" in t or "ночью" in t:
            hour = hour_match.group(1) if hour_match else "0"
        return f"0 {hour} * * *"

    # Hourly
    if any(w in t for w in ["каждый час", "hourly", "every hour"]):
        return "0 * * * *"

    # Every N minutes
    min_match = re.search(r'каждые?\s+(\d+)\s+минут', t) or re.search(r'every\s+(\d+)\s+min', t)
    if min_match:
        mins = int(min_match.group(1))
        if mins < 5:
            raise ValueError("Минимальный интервал — 5 минут")
        return f"*/{mins} * * * *"

    # Weekly patterns
    days = {
        "понедельник": 1, "вторник": 2, "среда": 3, "четверг": 4,
        "пятниц": 5, "суббот": 6, "воскресень": 0,
        "monday": 1, "tuesday": 2, "wednesday": 3, "thursday": 4,
        "friday": 5, "saturday": 6, "sunday": 0,
    }
    for day_word, day_num in days.items():
        if day_word in t:
            return f"0 {hour} * * {day_num}"

    if any(w in t for w in ["раз в неделю", "еженедельно", "weekly", "once a week"]):
        return f"0 {hour} * * 1"

    # Monthly
    if any(w in t for w in ["раз в месяц", "ежемесячно", "monthly", "once a month"]):
        return f"0 {hour} 1 * *"

    # Morning/evening shortcuts
    if "утр" in t:
        return f"0 {hour if hour_match else '8'} * * *"
    if "вечер" in t:
        return f"0 {hour if hour_match else '19'} * * *"

    raise ValueError(f"Не понял время: '{text}'. Примеры: 'каждое утро в 8', 'по понедельникам в 9', 'каждый день в 18'.")


@chat.function(
    "add_schedule",
    description=(
        "Add a scheduled notification to a bot. "
        "task_type: 'analytics_daily' (daily traffic), 'analytics_weekly' (weekly report), "
        "'custom_message' (fixed text). "
        "cron_expr examples: '0 8 * * *' = 8am daily, '0 9 * * 1' = 9am every Monday."
    ),
    action_type="write",
    chain_callable=True,
    effects=["create:schedule"],
    event="tgbot.schedule.created",
)
async def fn_add_schedule(ctx, params: AddScheduleParams) -> ActionResult:
    if params.task_type not in VALID_TASK_TYPES:
        return ActionResult.error(
            error=f"Неверный тип задачи. Выбери один из: {', '.join(VALID_TASK_TYPES)}"
        )

    # Natural language cron parsing
    cron_expr = params.cron_expr
    try:
        cron_expr = _parse_cron_natural(params.cron_expr)
    except ValueError as e:
        return ActionResult.error(error=str(e))

    name = await _resolve_bot_name(ctx, params)
    bots = await get_cached_bots(ctx)
    bot = next((b for b in bots if b["name"] == name), None)
    if not bot:
        return ActionResult.error(error=f"Бот '{name}' не найден.")

    settings = await load_settings(ctx)
    task_config: dict = {}

    if params.task_type in ("analytics_daily", "analytics_weekly"):
        task_config = {
            "matomo_url":     settings.get("matomo_url", ""),
            "matomo_token":   settings.get("matomo_token", ""),
            "matomo_site_id": settings.get("matomo_site_id", 1),
        }
        if not task_config["matomo_url"] or not task_config["matomo_token"]:
            return ActionResult.error(
                error="Matomo credentials not configured. Add them in WP Blogger Settings first."
            )

    if params.task_type == "custom_message":
        task_config = {"message": params.message or "Hello from your bot!"}

    result = await mos_add_schedule(
        ctx, bot["id"], cron_expr, params.description,
        params.task_type, task_config,
    )
    if "error" in result:
        return ActionResult.error(error=result["error"])
    return ActionResult.success(
        result,
        summary=f"Schedule added for '{params.bot_name}': {params.description} ({params.cron_expr})",
    )


@chat.function(
    "remove_schedule",
    description="Remove a scheduled notification by schedule ID.",
    action_type="destructive",
    chain_callable=True,
    effects=["delete:schedule"],
    event="tgbot.schedule.deleted",
)
async def fn_remove_schedule(ctx, params: RemoveScheduleParams) -> ActionResult:
    await mos_remove_schedule(ctx, params.schedule_id)
    return ActionResult.success({}, summary="Schedule removed.")


@chat.function(
    "list_schedules",
    description="List all schedules for a bot.",
    action_type="read",
    event="tgbot.schedule.listed",
)
async def fn_list_schedules(ctx, params: BotNameParams) -> ActionResult:
    bots = await mos_list_bots(ctx)
    bot = next((b for b in bots if b["name"] == params.bot_name), None)
    if not bot:
        return ActionResult.error(error=f"Bot '{params.bot_name}' not found.")
    schedules = await mos_list_schedules(ctx, bot["id"])
    return ActionResult.success(
        {"schedules": schedules, "total": len(schedules)},
        summary=f"{len(schedules)} schedule(s) for '{params.bot_name}'.",
    )
