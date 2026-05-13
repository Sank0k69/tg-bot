"""Center panel — guided bot creation wizard + detail views."""
from __future__ import annotations

from imperal_sdk import ui
from app import ext, get_cached_bots
from api_client import mos_list_schedules

NAV_COLLECTION = "tgbot_nav"

_BOTFATHER_QR = (
    "https://api.qrserver.com/v1/create-qr-code/"
    "?size=180x180&data=https%3A%2F%2Ft.me%2FBotFather"
)


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


# ── Wizard step 1 ────────────────────────────────────────────────────────────

def _step1_view() -> ui.UINode:
    return ui.Stack(children=[
        ui.Header(text="Создать Telegram-бота"),
        ui.Alert(type="info", message="Займёт 2 минуты. Просто следуй шагам."),
        ui.Divider(),
        ui.Stack(direction="row", children=[
            ui.Image(src=_BOTFATHER_QR, alt="QR BotFather", width=160),
            ui.Stack(children=[
                ui.Text(content="1. Отсканируй QR или открой @BotFather в Telegram"),
                ui.Text(content="2. Отправь команду /newbot"),
                ui.Text(content="3. Введи любое имя для бота"),
                ui.Text(content="4. Скопируй токен — он выглядит так:"),
                ui.Text(content="   1234567890:AABBBCCC_abc..."),
            ]),
        ]),
        ui.Divider(),
        ui.Form(
            action="show_step2_form",
            children=[],
            submit_label="У меня есть токен →",
        ),
    ])


# ── Wizard step 2 ────────────────────────────────────────────────────────────

def _step2_view() -> ui.UINode:
    return ui.Stack(children=[
        ui.Header(text="Подключить бота"),
        ui.Text(content="Вставь токен, который дал @BotFather:"),
        ui.Form(
            action="create_bot",
            submit_label="Создать бота 🚀",
            children=[
                ui.Input(
                    param_name="token",
                    placeholder="Вставь токен сюда (1234567890:AAABBB...)",
                ),
                ui.Input(
                    param_name="name",
                    placeholder="Название бота (для тебя, любое)",
                ),
            ],
        ),
        ui.Form(
            action="show_create_form",
            children=[],
            submit_label="← Назад",
        ),
    ])


# ── After creation: unlinked ─────────────────────────────────────────────────

def _unlinked_view(bot: dict) -> ui.UINode:
    invite_link = bot.get("invite_link", "")
    qr = bot.get("qr_base64", "")
    children = [
        ui.Header(text="Бот создан! Теперь подключи его к себе."),
        ui.Alert(type="success", message="Отсканируй QR в Telegram → нажми START. Готово!"),
    ]
    if qr:
        children.append(ui.Image(src=f"data:image/png;base64,{qr}", alt="QR", width=200))
    if invite_link:
        children.append(ui.Text(content=f"Или открой: {invite_link}"))
    children.append(
        ui.Alert(type="info", message="Панель обновится автоматически после подключения."),
    )
    return ui.Stack(children=children)


# ── Bot detail ────────────────────────────────────────────────────────────────

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
                    children=[ui.Input(param_name="schedule_id", placeholder=s["id"])],
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


# ── Main panel ────────────────────────────────────────────────────────────────

@ext.panel(
    "main",
    slot="center",
    title="TG Bot Builder",
    icon="MessageCircle",
    refresh="on_event:tgbot.created,tgbot.deleted,tgbot.updated,tgbot.listed,tgbot.nav_create,tgbot.nav_step2,tgbot.nav_detail",
)
async def main_panel(ctx, active_view: str = "list", selected_bot_id: str = None,
                     note_id: str = None):
    """Center panel: guided wizard / detail / list views."""
    bots = await get_cached_bots(ctx)

    # Store-based navigation from sidebar / back buttons
    nav_view = await _get_nav_view(ctx)
    if nav_view == "create":
        return _step1_view()
    if nav_view == "step2":
        return _step2_view()
    if nav_view and nav_view.startswith("detail:"):
        bot_id = nav_view.split(":", 1)[1]
        bot = next((b for b in bots if b["id"] == bot_id), None)
        if bot:
            schedules = await mos_list_schedules(ctx, bot_id)
            return _detail_view(bot, schedules)

    # URL param navigation
    if active_view == "create":
        return _step1_view()
    if active_view == "step2":
        return _step2_view()
    if active_view == "unlinked" and selected_bot_id:
        bot = next((b for b in bots if b["id"] == selected_bot_id), None)
        if bot:
            return _unlinked_view(bot)
    if active_view == "detail" and selected_bot_id:
        bot = next((b for b in bots if b["id"] == selected_bot_id), None)
        if bot:
            schedules = await mos_list_schedules(ctx, selected_bot_id)
            return _detail_view(bot, schedules)

    # No bots → start wizard
    if not bots:
        return _step1_view()

    # Bot list
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
