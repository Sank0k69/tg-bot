"""Settings handlers."""
from __future__ import annotations

from imperal_sdk import ActionResult
from imperal_sdk.types import ActionResult  # noqa: F811

from app import chat, load_settings, save_settings
from params import SaveSettingsParams, EmptyParams


@chat.function(
    "save_settings",
    description="Save TG Bot Builder settings (e.g. default bot ID for IPC).",
    action_type="write",
    chain_callable=True,
    effects=["update:settings"],
    event="tgbot.settings.saved",
)
async def fn_save_settings(ctx, params: SaveSettingsParams) -> ActionResult:
    """Save settings to ctx.store."""
    values = {k: v for k, v in params.dict().items() if v is not None}
    await save_settings(ctx, values)
    return ActionResult.success({}, summary="Settings saved.")


@chat.function(
    "get_settings",
    description="Show TG Bot Builder extension settings.",
    action_type="read",
    event="",
)
async def fn_get_settings(ctx, params: EmptyParams) -> ActionResult:
    """Return current settings."""
    settings = await load_settings(ctx)
    return ActionResult.success(settings, summary="Settings loaded.")
