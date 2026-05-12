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
    refresh="on_event:tgbot.created,tgbot.deleted,tgbot.updated",
)
async def sidebar_panel(ctx):
    """Left sidebar: bot list with status badges and create button."""
    bots = await get_cached_bots(ctx)

    create_btn = ui.Form(action="create_bot", children=[], submit_label="+ Создать бота")

    if not bots:
        return ui.Stack(children=[
            create_btn,
            ui.Empty(message="Ботов нет. Создай первого!"),
        ])

    bot_items = []
    for b in bots:
        bot_items.append(
            ui.Stack(
                direction="row",
                children=[
                    ui.Button(
                        label=b["name"],
                        on_click=ui.Call(
                            "__panel__main",
                            active_view="detail",
                            selected_bot_id=b["id"],
                            note_id="board",
                        ),
                    ),
                    _status_badge(b),
                ],
            )
        )

    return ui.Stack(children=[create_btn, ui.Divider(), *bot_items])
