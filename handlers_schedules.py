"""Schedule management chat functions."""
from __future__ import annotations

from imperal_sdk import ActionResult
from imperal_sdk.types import ActionResult  # noqa: F811

from app import chat, load_settings
from params import AddScheduleParams, RemoveScheduleParams, BotNameParams
from tgbot_api import mos_list_bots, mos_add_schedule, mos_remove_schedule, mos_list_schedules

VALID_TASK_TYPES = ("analytics_daily", "analytics_weekly", "custom_message")


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
            error=f"Invalid task_type. Choose: {', '.join(VALID_TASK_TYPES)}"
        )
    bots = await mos_list_bots(ctx)
    bot = next((b for b in bots if b["name"] == params.bot_name), None)
    if not bot:
        return ActionResult.error(error=f"Bot '{params.bot_name}' not found.")

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
        ctx, bot["id"], params.cron_expr, params.description,
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
