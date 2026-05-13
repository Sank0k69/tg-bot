"""Center panel — create / unlinked / detail views."""
from __future__ import annotations

from imperal_sdk import ui
from app import ext, get_cached_bots
from api_client import mos_list_schedules

NAV_COLLECTION = "tgbot_nav"


async def _get_nav_view(ctx) -> str:
    """Read pending nav view from store, then clear it."""
    try:
        page = await ctx.store.query(NAV_COLLECTION, limit=1)
        docs = getattr(page, "data", None) or []
        if docs and isinstance(getattr(docs[0], "data", None), dict):
            view = docs[0].data.get("view", "")
            if view:
                await ctx.store.update(NAV_COLLECTION, docs[0].id, {"view": ""})
            return view
    except Exception:
        pass
    return ""


def _create_view() -> ui.UINode:
    return ui.Stack(children=[
        ui.Header(text="Создать Telegram-бота"),
        ui.Form(
            action="create_bot",
            submit_label="Создать бота",
            children=[
                ui.Input(param_name="name", placeholder="Название бота"),
                ui.Input(param_name="token", placeholder="TG Bot Token из @BotFather"),
                ui.TextArea(param_name="system_prompt",
                            placeholder="Системный промпт (например: Ты помощник по аналитике...)"),
                ui.Select(
                    param_name="mode",
                    placeholder="Режим",
                    options=[
                        {"value": "standalone", "label": "Standalone (кастомный AI)"},
                        {"value": "webbee", "label": "Webbee (полный доступ к Imperal)"},
                    ],
                ),
                ui.Input(
                    param_name="owner_tg_id",
                    placeholder="Твой Telegram ID (необязательно — альтернатива QR)",
                ),
            ],
        ),
        ui.Alert(type="info", message="Получи токен в @BotFather → /newbot → скопируй токен."),
    ])


def _unlinked_view(bot: dict) -> ui.UINode:
    invite_link = bot.get("invite_link", "")
    qr = bot.get("qr_base64", "")
    children = [
        ui.Header(text=f"Бот \"{bot['name']}\" создан!"),
        ui.Alert(type="success", message="Отсканируй QR — Telegram откроется на боте. Нажми START."),
    ]
    if qr:
        children.append(ui.Image(src=f"data:image/png;base64,{qr}", alt="QR код", width=200))
    children += [
        ui.Text(content=invite_link or "Ссылка недоступна"),
        ui.Alert(type="info", message="QR действителен 24 часа. После истечения — нажми 'Перепривязать'."),
        ui.Text(content="Панель обновится автоматически после привязки."),
    ]
    return ui.Stack(children=children)


def _detail_view(bot: dict, schedules: list) -> ui.UINode:
    if bot.get("owner_chat_id") and bot.get("enabled"):
        status = "Active"
    elif not bot.get("owner_chat_id"):
        status = "Unlinked"
    else:
        status = "Disabled"

    sched_items = []
    for s in schedules:
        sched_items.append(
            ui.Stack(direction="row", children=[
                ui.Text(content=f"{s['cron_expr']}  {s['description']}  ({s['task_type']})"),
                ui.Form(
                    action="remove_schedule",
                    children=[
                        ui.Input(param_name="schedule_id", placeholder=s["id"]),
                    ],
                    submit_label="✕",
                ),
            ])
        )

    return ui.Stack(children=[
        ui.Stack(direction="row", children=[
            ui.Header(text=f"{bot['name']}  [{status}]"),
            ui.Form(
                action="disable_bot" if bot.get("enabled") else "enable_bot",
                children=[ui.Input(param_name="bot_name", placeholder=bot["name"])],
                submit_label="Отключить" if bot.get("enabled") else "Включить",
            ),
            ui.Form(
                action="delete_bot",
                children=[ui.Input(param_name="bot_name", placeholder=bot["name"])],
                submit_label="Удалить",
            ),
        ]),
        ui.Text(content=f"@{bot.get('bot_username', '')} | Режим: {bot.get('mode', 'standalone')}"),
        ui.Divider(),
        ui.Section(title="Системный промпт", collapsible=True, children=[
            ui.Text(content=bot.get("system_prompt") or "(не задан)"),
            ui.Form(
                action="set_prompt",
                submit_label="Обновить промпт",
                children=[
                    ui.Input(param_name="bot_name", placeholder=bot["name"]),
                    ui.TextArea(param_name="system_prompt", placeholder="Новый промпт..."),
                ],
            ),
        ]),
        ui.Divider(),
        ui.Section(title="Расписания", collapsible=True, children=[
            *sched_items,
            ui.Form(
                action="add_schedule",
                submit_label="+ Добавить расписание",
                children=[
                    ui.Input(param_name="bot_name", placeholder=bot["name"]),
                    ui.Input(param_name="description", placeholder="Описание задачи"),
                    ui.Input(param_name="cron_expr", placeholder="Cron: 0 8 * * *"),
                    ui.Select(
                        param_name="task_type",
                        placeholder="Тип задачи",
                        options=[
                            {"value": "analytics_daily", "label": "Трафик за сутки"},
                            {"value": "analytics_weekly", "label": "Недельный отчёт"},
                            {"value": "custom_message", "label": "Текстовое сообщение"},
                        ],
                    ),
                    ui.Input(param_name="message", placeholder="Текст (для custom_message)"),
                ],
            ),
        ]),
        ui.Divider(),
        ui.Section(title="Тест и управление", collapsible=True, children=[
            ui.Form(
                action="test_bot",
                children=[ui.Input(param_name="bot_name", placeholder=bot["name"])],
                submit_label="Отправить тестовое сообщение",
            ),
            ui.Form(
                action="relink_bot",
                children=[ui.Input(param_name="bot_name", placeholder=bot["name"])],
                submit_label="Перепривязать бота",
            ),
        ]),
    ])


@ext.panel(
    "main",
    slot="center",
    title="TG Bot Builder",
    icon="MessageCircle",
    refresh="on_event:tgbot.created,tgbot.deleted,tgbot.updated,tgbot.listed,tgbot.nav_create,tgbot.nav_detail",
)
async def main_panel(ctx, active_view: str = "list", selected_bot_id: str = None,
                     note_id: str = None):
    """Center panel: create / unlinked / detail / list views."""
    bots = await get_cached_bots(ctx)

    # Check store-based navigation (fired from sidebar buttons)
    nav_view = await _get_nav_view(ctx)
    if nav_view == "create":
        return _create_view()
    if nav_view and nav_view.startswith("detail:"):
        bot_id = nav_view.split(":", 1)[1]
        bot = next((b for b in bots if b["id"] == bot_id), None)
        if bot:
            schedules = await mos_list_schedules(ctx, bot_id)
            return _detail_view(bot, schedules)

    if active_view == "create":
        return _create_view()

    if active_view == "unlinked" and selected_bot_id:
        bot = next((b for b in bots if b["id"] == selected_bot_id), None)
        if bot:
            return _unlinked_view(bot)

    if active_view == "detail" and selected_bot_id:
        bot = next((b for b in bots if b["id"] == selected_bot_id), None)
        if bot:
            schedules = await mos_list_schedules(ctx, selected_bot_id)
            return _detail_view(bot, schedules)

    # No bots — show create form directly
    if not bots:
        return _create_view()

    rows = [
        ui.Stack(direction="row", children=[
            ui.Text(content=b["name"]),
            ui.Badge(
                label="Active" if b.get("owner_chat_id") and b.get("enabled") else
                       "Unlinked" if not b.get("owner_chat_id") else "Disabled",
                color="green" if b.get("owner_chat_id") and b.get("enabled") else
                       "orange" if not b.get("owner_chat_id") else "red",
            ),
            ui.Form(
                action="open_bot_detail",
                children=[ui.Input(param_name="bot_id", placeholder=b["id"])],
                submit_label="Открыть",
            ),
        ])
        for b in bots
    ]
    return ui.Stack(children=[
        ui.Header(text="Мои боты"),
        ui.Form(action="show_create_form", children=[], submit_label="+ Создать бота"),
        ui.Divider(),
        *rows,
    ])
