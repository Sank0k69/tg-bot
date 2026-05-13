"""Left sidebar — bot list with status badges."""
from __future__ import annotations

from imperal_sdk import ui
from app import ext, get_cached_bots


def _status_badge(bot: dict) -> ui.UINode:
    if not bot.get("enabled"):
        return ui.Badge(label="Disabled", color="red")
    if not bot.get("owner_chat_id"):
        return ui.Badge(label="Unlinked", color="orange")
    return ui.Badge(label="Active", color="green")


@ext.panel(
    "sidebar",
    slot="left",
    title="TG Боты",
    icon="MessageCircle",
    default_width=220,
    refresh="on_event:tgbot.created,tgbot.deleted,tgbot.updated,tgbot.nav_create",
)
async def sidebar_panel(ctx):
    bots = await get_cached_bots(ctx)

    create_btn = ui.Form(action="show_create_form", children=[], submit_label="+ Создать бота")

    if not bots:
        return ui.Stack(children=[
            create_btn,
            ui.Empty(message="Ботов нет. Создай первого!"),
        ])

    bot_items = []
    for b in bots:
        bot_items.append(
            ui.Stack(direction="row", children=[
                ui.Text(content=b["name"]),
                _status_badge(b),
                ui.Form(
                    action="open_bot_detail",
                    children=[ui.Input(param_name="bot_id", value=b["id"])],
                    submit_label="Открыть",
                ),
            ])
        )

    return ui.Stack(children=[create_btn, ui.Divider(), *bot_items])
