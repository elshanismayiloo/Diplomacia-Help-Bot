# -*- coding: utf-8 -*-
"""
Diplomacia Profit Calculator - Telegram Bot

İşə salmaq üçün:
1. pip install -r requirements.txt
2. export TELEGRAM_BOT_TOKEN="sizin_token"
3. python bot.py
"""
import os
import asyncio
import logging

from telegram import (
    Update, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, MenuButtonCommands,
)
from telegram.error import BadRequest
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ConversationHandler,
    MessageHandler, CallbackQueryHandler, ContextTypes, filters,
    PicklePersistence,
)

from calculator import (
    GameInput, ResourceInput, full_analysis, order_resources, format_duration,
    humanize_m, humanize_number, format_price,
    try_parse_money, try_parse_package_price, RESOURCE_UNITS, RESOURCE_ORDER, MARKET_BATCH_SIZE,
)
import telegraph_setup
import price_history

logging.basicConfig(level=logging.INFO)

(MODE, HEALTH, DIAMONDS, PKG_DIAMONDS, PKG_PRICE,
 RESOURCE_SELECT, BONUS_YN, BONUS_RESOURCE,
 COLLECT_PRODUCTION, COLLECT_ALT_PRODUCTION, BONUS_VALUE, COLLECT_PRICE) = range(12)

BIG_NUMBER_HINT = "(rəqəmi istənilən formatda yaza bilərsən: 50000, 50k, 1m, 1M, 1kkk)"

SKIP_PRICE_ROW = [[InlineKeyboardButton("⏭ Hesablamaq istəmirəm", callback_data="skip_price")]]
SKIP_PRICE_KB = InlineKeyboardMarkup(SKIP_PRICE_ROW)

# Rəqəm klaviaturasının hansı "addım" üçün açıldığını uyğun ConversationHandler
# state-inə bağlayır (klaviaturadan basılan düymələr bu lüğət vasitəsilə
# düzgün state-ə yönləndirilir).
STEP_STATE = {
    "health": HEALTH,
    "diamonds": DIAMONDS,
    "pkg_diamonds": PKG_DIAMONDS,
    "pkg_price": PKG_PRICE,
    "production": COLLECT_PRODUCTION,
    "alt_production": COLLECT_ALT_PRODUCTION,
    "bonus_value": BONUS_VALUE,
    "price": COLLECT_PRICE,
}

NUMPAD_MAX_LEN = 15

# Hər resursun son daxil edilmiş istehsal (və bonussuz istehsal) miqdarını
# yadda saxlayır ki, növbəti dəfə eyni resursu seçəndə təklif oluna bilsin.
PRODUCTION_PROFILE_KEY = "production_profile"

# Sabit (persistent) klaviaturadakı təmiz düymə adları (slash-komanda görünmür,
# yalnız emoji + söz). Bu mətnlər gəldikdə uyğun funksiya çağırılır.
BUTTON_START = "🚀 Başla"
BUTTON_HELP = "❓ Kömək"
BUTTON_QIYMETLER = "📈 Qiymətlər"
BUTTON_CANCEL = "❌ Ləğv et"

# ---------- Klaviaturalar ----------

def mode_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Mövcud balansımla", callback_data="mode_balance")],
        [InlineKeyboardButton("🛒 Yeni almaz paketi alaraq", callback_data="mode_package")],
    ])


def bonus_yn_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Bəli", callback_data="bonus_yes"),
         InlineKeyboardButton("Xeyr", callback_data="bonus_no")],
    ])


def bonus_resource_select_keyboard(selected: set, options):
    row = [InlineKeyboardButton(f"✅ {r}" if r in selected else r, callback_data=f"bonusres_toggle_{r}")
           for r in options]
    return InlineKeyboardMarkup([
        row,
        [InlineKeyboardButton("✅ Hamısını seç", callback_data="bonusres_all")],
        [InlineKeyboardButton("▶️ Davam et", callback_data="bonusres_continue")],
    ])


def resource_select_keyboard(selected: set):
    row = []
    for r in RESOURCE_ORDER:
        label = f"✅ {r}" if r in selected else r
        row.append(InlineKeyboardButton(label, callback_data=f"res_toggle_{r}"))
    return InlineKeyboardMarkup([
        row,
        [InlineKeyboardButton("✅ Hamısını seç", callback_data="res_all")],
        [InlineKeyboardButton("▶️ Davam et", callback_data="res_continue")],
    ])


def resource_label(name: str, bonus_resources):
    return f"🎁{name}" if name in (bonus_resources or ()) else name


def commands_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(BUTTON_START), KeyboardButton(BUTTON_HELP)],
            [KeyboardButton(BUTTON_QIYMETLER), KeyboardButton(BUTTON_CANCEL)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def numpad_keyboard(extra_rows=None):
    """4x4 rəqəm klaviaturası: 0-9, nöqtə, K (min), M (milyon), 000, ⌫ və ✅.

    Bu, sistemin adi qwerty klaviaturasını əvəz etmək üçün mesaja bağlı
    (inline) düymələrdir - istifadəçi rəqəmi yazmaq üçün adi klaviaturanı
    açmaq məcburiyyətində qalmır.
    """
    def b(label, token):
        return InlineKeyboardButton(label, callback_data=f"np_{token}")

    rows = [
        [b("1", "1"), b("2", "2"), b("3", "3"), b("⌫", "back")],
        [b("4", "4"), b("5", "5"), b("6", "6"), b("K", "k")],
        [b("7", "7"), b("8", "8"), b("9", "9"), b("M", "m")],
        [b(".", "dot"), b("0", "0"), b("000", "000"), b("✅", "ok")],
    ]
    if extra_rows:
        rows = rows + list(extra_rows)
    return InlineKeyboardMarkup(rows)


NUMPAD_TOKEN_TO_CHAR = {
    "0": "0", "1": "1", "2": "2", "3": "3", "4": "4",
    "5": "5", "6": "6", "7": "7", "8": "8", "9": "9",
    "dot": ".", "000": "000", "k": "k", "m": "M",
}


def render_numpad_text(prompt: str, buffer: str) -> str:
    shown = buffer if buffer else "—"
    return f"{prompt}\n\n🔢 Daxil etdiyin: {shown}"


def _clear_numpad_state(context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("numpad_buffer", None)
    context.user_data.pop("numeric_step", None)
    context.user_data.pop("numpad_prompt", None)
    context.user_data.pop("numpad_extra_rows", None)


BACK_ROW = [[InlineKeyboardButton("◀️ Geri (düzəliş et)", callback_data="np_goback")]]


async def send_numpad_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE,
                              step: str, prompt: str, extra_rows=None, prefill: str = ""):
    context.user_data["numeric_step"] = step
    context.user_data["numpad_buffer"] = prefill or ""
    context.user_data["numpad_prompt"] = prompt
    rows = list(extra_rows) if extra_rows else []
    if context.user_data.get("nav_stack"):
        rows = rows + BACK_ROW
    context.user_data["numpad_extra_rows"] = rows
    await update.effective_message.reply_text(
        render_numpad_text(prompt, context.user_data["numpad_buffer"]),
        reply_markup=numpad_keyboard(rows),
    )


async def _safe_edit_text(query, text: str, reply_markup):
    try:
        await query.edit_message_text(text, reply_markup=reply_markup)
    except BadRequest:
        pass


def _format_prefill(value) -> str:
    if value is None:
        return ""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value)
    return str(int(f)) if f.is_integer() else str(f)


async def numpad_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    step = context.user_data.get("numeric_step")
    if step not in STEP_STATE:
        # Köhnəlmiş/artıq təsdiqlənmiş klaviaturaya basılıb - sadəcə cavab ver.
        await query.answer()
        return ConversationHandler.END

    token = query.data[len("np_"):]

    if token == "goback":
        stack = context.user_data.get("nav_stack", [])
        if not stack:
            await query.answer("⬅️ Geri qayıdacaq addım yoxdur.", show_alert=True)
            return STEP_STATE[step]
        entry = stack.pop()
        await query.answer()
        reask_fn = REASK_DISPATCH[entry["kind"]]
        return await reask_fn(update, context, _format_prefill(entry.get("value")))

    if token == "ok":
        buffer = context.user_data.get("numpad_buffer", "")
        if not buffer:
            await query.answer("⚠️ Əvvəlcə rəqəm daxil et.", show_alert=True)
            return STEP_STATE[step]
        prompt = context.user_data.get("numpad_prompt", "")
        # answer() və edit_message_text() ardıcıl deyil, paralel göndərilir -
        # bu, hər basılışdan sonra rəqəmin ekranda görünmə gecikməsini azaldır.
        await asyncio.gather(
            query.answer(),
            _safe_edit_text(query, f"{prompt}\n\n✅ {buffer}", InlineKeyboardMarkup([])),
        )
        handler_fn = STEP_HANDLER[step]
        _clear_numpad_state(context)
        return await handler_fn(update, context, raw_text=buffer)

    buffer = context.user_data.get("numpad_buffer", "")
    if token == "back":
        buffer = buffer[:-1]
    elif len(buffer) < NUMPAD_MAX_LEN:
        buffer += NUMPAD_TOKEN_TO_CHAR.get(token, "")
    context.user_data["numpad_buffer"] = buffer

    prompt = context.user_data.get("numpad_prompt", "")
    extra_rows = context.user_data.get("numpad_extra_rows")
    await asyncio.gather(
        query.answer(),
        _safe_edit_text(query, render_numpad_text(prompt, buffer), numpad_keyboard(extra_rows)),
    )
    return STEP_STATE[step]


# ---------- Başlanğıc ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    saved_profile = context.user_data.get(PRODUCTION_PROFILE_KEY)
    context.user_data.clear()
    if saved_profile:
        context.user_data[PRODUCTION_PROFILE_KEY] = saved_profile
    text = (
        "Salam! Diplomacia Gəlir Hesablayıcısına xoş gəldin.\n\n"
        "Lazımi rəqəmləri oyunda necə tapacağını bilmirsənsə, ❓️Kömək (/help) düyməsi ilə öyrənə bilərsən.\n\n"
        "İstənilən vaxt ❌️ Ləğv et (/cancel) düyməsi ilə hesablamanı dayandıra bilərsən.\n\n"
        "🔢 Böyük rəqəm tələb olunan suallarda istənilən formatda yaza bilərsən\n"
        "(50000, 50k, 1m, 1M, 1kkk).\n\n"
        "Necə hesablamaq istəyirsən?"
    )
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(text, reply_markup=mode_keyboard())
    else:
        await update.message.reply_text(text, reply_markup=commands_keyboard())
        await update.message.reply_text("Seçim et:", reply_markup=mode_keyboard())
    return MODE


async def mode_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["use_existing_balance"] = (query.data == "mode_balance")
    await query.edit_message_text("Seçim qeydə alındı ✅")
    await send_numpad_prompt(update, context, "health", "Cari 💊 (sağlıq həbi) balansın neçədir?")
    return HEALTH


# ---------- Balans ----------

async def health(update: Update, context: ContextTypes.DEFAULT_TYPE, raw_text=None):
    text = raw_text if raw_text is not None else update.message.text
    value = try_parse_money(text)
    if value is None:
        await update.effective_message.reply_text("⚠️ Rəqəm kimi tanınmadı. Zəhmət olmasa yenidən yaz (məs: 50000 və ya 50k).")
        return HEALTH
    context.user_data["health"] = value
    context.user_data.setdefault("nav_stack", []).append({"kind": "health", "value": value})
    await send_numpad_prompt(update, context, "diamonds", "Cari 💎 (almaz) balansın neçədir?")
    return DIAMONDS


async def diamonds(update: Update, context: ContextTypes.DEFAULT_TYPE, raw_text=None):
    text = raw_text if raw_text is not None else update.message.text
    value = try_parse_money(text)
    if value is None:
        await update.effective_message.reply_text("⚠️ Rəqəm kimi tanınmadı. Zəhmət olmasa yenidən yaz (məs: 40000 və ya 40k).")
        return DIAMONDS
    context.user_data["diamonds"] = value
    context.user_data.setdefault("nav_stack", []).append({"kind": "diamonds", "value": value})
    if context.user_data.get("use_existing_balance"):
        return await ask_resource_select(update, context)
    await send_numpad_prompt(update, context, "pkg_diamonds", "Almaz paketində neçə 💎 var? (məs: 50000)")
    return PKG_DIAMONDS


async def pkg_diamonds(update: Update, context: ContextTypes.DEFAULT_TYPE, raw_text=None):
    text = raw_text if raw_text is not None else update.message.text
    value = try_parse_money(text)
    if value is None:
        await update.effective_message.reply_text("⚠️ Rəqəm kimi tanınmadı. Zəhmət olmasa yenidən yaz (məs: 50000 və ya 50k).")
        return PKG_DIAMONDS
    context.user_data["package_diamonds"] = value
    context.user_data.setdefault("nav_stack", []).append({"kind": "pkg_diamonds", "value": value})
    await send_numpad_prompt(update, context, "pkg_price", "Həmin paketin qiyməti neçə M-dir? (məs: 120M)")
    return PKG_PRICE


async def pkg_price(update: Update, context: ContextTypes.DEFAULT_TYPE, raw_text=None):
    text = raw_text if raw_text is not None else update.message.text
    value = try_parse_package_price(text)
    if value is None:
        await update.effective_message.reply_text("⚠️ Rəqəm kimi tanınmadı. Zəhmət olmasa yenidən yaz (məs: 120M).")
        return PKG_PRICE
    context.user_data["package_price_m"] = value
    return await ask_resource_select(update, context)


# ---------- Resurs seçimi ----------

async def ask_resource_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["selected"] = set()
    context.user_data["nav_stack"] = []
    text = "Hansı resurs(lar) üçün hesablamaq istəyirsən?"
    kb_text = "Bir və ya bir neçə resurs seç, sonra 'Davam et' düyməsinə bas:"
    await update.effective_message.reply_text(text)
    await update.effective_message.reply_text(kb_text, reply_markup=resource_select_keyboard(set()))
    return RESOURCE_SELECT


async def resource_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    selected = context.user_data.setdefault("selected", set())
    if query.data == "res_all":
        selected.clear()
        selected.update(RESOURCE_ORDER)
    elif query.data == "res_continue":
        if not selected:
            await query.answer("Zəhmət olmasa ən azı 1 resurs seç.", show_alert=True)
            return RESOURCE_SELECT
        context.user_data["ordered_selected"] = order_resources(selected)
        await query.edit_message_text(f"Seçildi: {' '.join(context.user_data['ordered_selected'])}")
        await query.message.reply_text("Bonuslu fabrikin var mı?", reply_markup=bonus_yn_keyboard())
        return BONUS_YN
    else:
        r = query.data.replace("res_toggle_", "")
        if r in selected:
            selected.discard(r)
        else:
            selected.add(r)
        await query.edit_message_reply_markup(reply_markup=resource_select_keyboard(selected))
        return RESOURCE_SELECT
    return RESOURCE_SELECT


# ---------- Bonus ----------

async def bonus_yn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "bonus_yes":
        context.user_data["bonus_resources_selecting"] = set()
        options = context.user_data["ordered_selected"]
        await query.edit_message_text(
            "Bonuslu fabrik(lər) hansı resurs(lar) üzrədir? (bir və ya bir neçəsini seç)",
            reply_markup=bonus_resource_select_keyboard(set(), options),
        )
        return BONUS_RESOURCE
    context.user_data["bonus_resources"] = set()
    return await start_resource_queue(update, context)


async def bonus_resource_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    selected = context.user_data.setdefault("bonus_resources_selecting", set())
    options = context.user_data["ordered_selected"]

    if query.data == "bonusres_all":
        selected.clear()
        selected.update(options)
    elif query.data == "bonusres_continue":
        if not selected:
            await query.answer("Zəhmət olmasa ən azı 1 resurs seç.", show_alert=True)
            return BONUS_RESOURCE
        context.user_data["bonus_resources"] = set(selected)
        await query.edit_message_text(f"Bonuslu fabrik(lər): {' '.join(order_resources(selected))}")
        return await start_resource_queue(update, context)
    else:
        r = query.data.replace("bonusres_toggle_", "")
        if r in selected:
            selected.discard(r)
        else:
            selected.add(r)

    await query.edit_message_reply_markup(reply_markup=bonus_resource_select_keyboard(selected, options))
    return BONUS_RESOURCE


async def start_resource_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["queue"] = list(context.user_data["ordered_selected"])
    context.user_data["finished_resources"] = []
    return await ask_next_production(update, context)


def price_now_prompt_text(context: ContextTypes.DEFAULT_TYPE) -> str:
    base = "İndiki bazar qiyməti neçədir?\n(bu resurs üçün gəlir hesablamaq istəmirsənsə, aşağıdakı düyməni basa bilərsən)"
    current = context.user_data.get("current_resource")
    stats = price_history.get_stats(context.bot_data, current) if current else None
    hint = price_history.format_inline_hint(current, stats) if stats else ""
    return f"{base}\n\n{hint}" if hint else base


# ---------- Resurs məlumatları (istehsal + qiymətlər) ----------

async def ask_next_production(update: Update, context: ContextTypes.DEFAULT_TYPE):
    queue = context.user_data["queue"]
    current = queue[0]
    context.user_data["current_resource"] = current
    context.user_data["price_step"] = 0
    unit = RESOURCE_UNITS.get(current, "ədəd")
    is_bonus_res = current in context.user_data.get("bonus_resources", set())
    bonus_note = " (bu, bonuslu fabrikindir)" if is_bonus_res else ""
    text = f"{current}{bonus_note} üçün 1 çalışmada nə qədər {unit} istehsal olunur?"

    extra_rows = None
    saved = context.user_data.get(PRODUCTION_PROFILE_KEY, {}).get(current)
    if saved and saved.get("production"):
        label = f"✅ Əvvəlki: {humanize_number(saved['production'])} {unit}"
        extra_rows = [[InlineKeyboardButton(label, callback_data="useprod_production")]]

    await send_numpad_prompt(update, context, "production", text, extra_rows=extra_rows)
    return COLLECT_PRODUCTION


async def _production_captured(update: Update, context: ContextTypes.DEFAULT_TYPE, value: float):
    context.user_data["current_production"] = value
    context.user_data.setdefault("nav_stack", []).append({"kind": "production", "value": value})
    current = context.user_data["current_resource"]
    is_bonus_res = current in context.user_data.get("bonus_resources", set())
    if is_bonus_res:
        unit = RESOURCE_UNITS.get(current, "ədəd")
        extra_rows = None
        saved = context.user_data.get(PRODUCTION_PROFILE_KEY, {}).get(current)
        if saved and saved.get("alt_production"):
            label = f"✅ Əvvəlki: {humanize_number(saved['alt_production'])} {unit}"
            extra_rows = [[InlineKeyboardButton(label, callback_data="useprod_alt_production")]]
        await send_numpad_prompt(
            update, context, "alt_production",
            f"Əgər bonus olmasaydı, 1 çalışmada nə qədər {unit} istehsal edə bilərsən?\n"
            "(bonuslu fabrikin, bonussuz ən yaxşı fabriklə müqayisəsi üçün lazımdır)",
            extra_rows=extra_rows,
        )
        return COLLECT_ALT_PRODUCTION
    context.user_data["price_step"] = 0
    await send_numpad_prompt(
        update, context, "price",
        price_now_prompt_text(context),
        extra_rows=SKIP_PRICE_ROW,
    )
    return COLLECT_PRICE


async def collect_production(update: Update, context: ContextTypes.DEFAULT_TYPE, raw_text=None):
    text = raw_text if raw_text is not None else update.message.text
    value = try_parse_money(text)
    if value is None:
        await update.effective_message.reply_text("⚠️ Rəqəm kimi tanınmadı. Zəhmət olmasa yenidən yaz.")
        return COLLECT_PRODUCTION
    return await _production_captured(update, context, value)


async def use_saved_production_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    current = context.user_data["current_resource"]
    saved = context.user_data.get(PRODUCTION_PROFILE_KEY, {}).get(current, {})
    field = "alt_production" if query.data == "useprod_alt_production" else "production"
    value = saved.get(field)
    if value is None:
        await query.answer("Əvvəlki dəyər tapılmadı.", show_alert=True)
        return COLLECT_PRODUCTION if field == "production" else COLLECT_ALT_PRODUCTION
    await query.answer()
    _clear_numpad_state(context)
    if field == "production":
        return await _production_captured(update, context, value)
    return await _alt_production_captured(update, context, value)


async def _alt_production_captured(update: Update, context: ContextTypes.DEFAULT_TYPE, value: float):
    context.user_data["current_alt_production"] = value
    context.user_data.setdefault("nav_stack", []).append({"kind": "alt_production", "value": value})
    await send_numpad_prompt(
        update, context, "bonus_value",
        f"Bonuslu fabrikdə 1 çalışma başına, istehsaldan əlavə, orta hesabla nə qədər ₼ bonus qazanırsan?\n{BIG_NUMBER_HINT}",
    )
    return BONUS_VALUE


async def collect_alt_production(update: Update, context: ContextTypes.DEFAULT_TYPE, raw_text=None):
    text = raw_text if raw_text is not None else update.message.text
    value = try_parse_money(text)
    if value is None:
        await update.effective_message.reply_text("⚠️ Rəqəm kimi tanınmadı. Zəhmət olmasa yenidən yaz.")
        return COLLECT_ALT_PRODUCTION
    return await _alt_production_captured(update, context, value)


async def bonus_value(update: Update, context: ContextTypes.DEFAULT_TYPE, raw_text=None):
    text = raw_text if raw_text is not None else update.message.text
    value = try_parse_money(text)
    if value is None:
        await update.effective_message.reply_text("⚠️ Rəqəm kimi tanınmadı. Zəhmət olmasa yenidən yaz (məs: 20000 və ya 20k).")
        return BONUS_VALUE
    context.user_data["current_bonus_per_work"] = value
    context.user_data.setdefault("nav_stack", []).append({"kind": "bonus_value", "value": value})
    context.user_data["price_step"] = 0
    await send_numpad_prompt(
        update, context, "price",
        price_now_prompt_text(context),
        extra_rows=SKIP_PRICE_ROW,
    )
    return COLLECT_PRICE


async def _handle_price_value(update: Update, context: ContextTypes.DEFAULT_TYPE, value: float):
    step = context.user_data.get("price_step", 0)
    if step == 0:
        if value == 0:
            context.user_data["current_price_now"] = None
            return await finish_current_resource(update, context)
        context.user_data["current_price_now"] = value
        price_history.record_price(context.bot_data, context.user_data["current_resource"], value)
        context.user_data.setdefault("nav_stack", []).append({"kind": "price_now", "value": value})
        context.user_data["price_step"] = 1
        await send_numpad_prompt(
            update, context, "price",
            "Bazar durğunlaşarsa minimum qiymət nə qədər olar?\n(hesablamaq istəmirsənsə aşağıdakı düyməni bas)",
            extra_rows=SKIP_PRICE_ROW,
        )
        return COLLECT_PRICE
    if step == 1:
        context.user_data["current_price_worst"] = None if value == 0 else value
        context.user_data.setdefault("nav_stack", []).append(
            {"kind": "price_worst", "value": context.user_data["current_price_worst"]}
        )
        context.user_data["price_step"] = 2
        await send_numpad_prompt(
            update, context, "price",
            "Bazar hərəkətlənərsə maksimum qiymət nə qədər olar?\n(hesablamaq istəmirsənsə aşağıdakı düyməni bas)",
            extra_rows=SKIP_PRICE_ROW,
        )
        return COLLECT_PRICE
    context.user_data["current_price_best"] = None if value == 0 else value
    return await finish_current_resource(update, context)


async def collect_price(update: Update, context: ContextTypes.DEFAULT_TYPE, raw_text=None):
    text = raw_text if raw_text is not None else update.message.text
    value = try_parse_money(text)
    if value is None:
        await update.effective_message.reply_text("⚠️ Rəqəm kimi tanınmadı. Zəhmət olmasa yenidən yaz (0 = keç).")
        return COLLECT_PRICE
    return await _handle_price_value(update, context, value)


async def skip_price_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _clear_numpad_state(context)
    return await _handle_price_value(update, context, 0.0)


async def finish_current_resource(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ud = context.user_data
    is_bonus = ud["current_resource"] in ud.get("bonus_resources", set())
    resource = ResourceInput(
        name=ud["current_resource"],
        production_per_work=ud["current_production"],
        price_now=ud.get("current_price_now"),
        price_worst=ud.get("current_price_worst"),
        price_best=ud.get("current_price_best"),
        is_bonus=is_bonus,
        alt_production_per_work=ud.get("current_alt_production"),
        bonus_per_work_m=ud.get("current_bonus_per_work"),
    )
    ud["finished_resources"].append(resource)
    ud["queue"].pop(0)
    ud["nav_stack"] = []
    profile = ud.setdefault(PRODUCTION_PROFILE_KEY, {})
    profile[resource.name] = {
        "production": resource.production_per_work,
        "alt_production": resource.alt_production_per_work,
    }
    for k in ("current_resource", "current_production", "current_price_now",
              "current_price_worst", "current_price_best", "current_alt_production",
              "current_bonus_per_work", "price_step"):
        ud.pop(k, None)
    if ud["queue"]:
        return await ask_next_production(update, context)
    await compute_and_send(update, context)
    return ConversationHandler.END


# ---------- Hesablama və nəticə ----------

async def compute_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ud = context.user_data
    game_input = GameInput(
        health=ud["health"], diamonds=ud["diamonds"],
        use_existing_balance=ud.get("use_existing_balance", True),
        package_diamonds=ud.get("package_diamonds", 0.0),
        package_price_m=ud.get("package_price_m", 0.0),
        resources=ud["finished_resources"],
    )
    result = full_analysis(game_input)
    reports_by_name = {r["name"]: r for r in result["reports"]}
    cost_per_work = result["cost_per_work_m"]
    bonus_resources = ud.get("bonus_resources", set())

    async def send(text):
        if update.callback_query:
            await update.callback_query.message.reply_text(text, parse_mode="Markdown")
        else:
            await update.message.reply_text(text, parse_mode="Markdown")

    header_lines = [
        "📊 *Nəticələr*",
        f"Çalışma sayı: *{int(result['total_works'])}*",
        f"Təxmini vaxt: *{format_duration(result['total_duration_seconds'])}*",
    ]
    if cost_per_work > 0:
        header_lines.append(f"1 çalışmanın maya dəyəri: *{humanize_m(cost_per_work)}*")
    else:
        header_lines.append("_Mövcud balansla hesablanır (maya dəyəri tətbiq olunmur)_")
    await send("\n".join(header_lines))

    for r in result["reports"]:
        unit = RESOURCE_UNITS.get(r["name"], "ədəd")
        label = resource_label(r["name"], bonus_resources)
        lines = [f"{label} — NƏTİCƏ", f"↳ İstehsal: {humanize_number(r['production'])} {unit}", ""]
        if r["market_batches"] > 0:
            lines.append(f"Bazarda satmaq üçün minimum {humanize_number(r['market_batches'])} dəfə satışa qoymalısan.")
            lines.append(f"(tək satışda maks {humanize_number(MARKET_BATCH_SIZE)} {unit})")
            lines.append("")
        if not r["has_price"]:
            lines.append("_Qiymət daxil edilmədiyi üçün gəlir hesablanmadı._")
            await send("\n".join(lines))
            continue
        n = r["now"]
        lines.append(f"↳ Gəlir: {humanize_m(n['gross_income_m'])}")
        lines.append("")
        lines.append(f"↳ Xalis qazanc: {humanize_m(n['net_income_m'])}")
        if cost_per_work > 0 and n["roi_percent"] is not None:
            lines.append(f"ROI: {n['roi_percent']:.2f}%")
            lines.append(f"Ümumi geri dönüş: {n['return_multiple']:.2f} dəfə")
            lines.append(f"Xalis geri dönüş: {n['net_multiple']:.2f} dəfə")
        lines.append("")
        if "worst" in r:
            lines.append(f"↳ Durğun bazarda: {humanize_m(r['worst']['net_income_m'])}")
        if "best" in r:
            lines.append(f"↳ Hərəkətli bazarda: {humanize_m(r['best']['net_income_m'])}")
        if "worst" in r or "best" in r:
            lines.append("")
        if "alt" in r:
            alt = r["alt"]
            diff = alt["diff_net_m"]
            if diff >= 0:
                lines.append(f"🎁 Bonus olmasaydı: {humanize_m(alt['now']['net_income_m'])}")
                lines.append(f"(bonus sənə {humanize_m(diff)} əlavə qazandırır)")
            else:
                lines.append(f"⚠️ Bonus olmasaydı: {humanize_m(alt['now']['net_income_m'])}")
                lines.append(f"(bonus əslində {humanize_m(abs(diff))} qazandırır - istehsal fərqinə görə)")
            lines.append("")
        if cost_per_work > 0:
            msp = r.get("min_sale_price")
            lines.append(f"Minimal satış qiyməti: {format_price(msp)}")
            if msp is not None and msp < 1:
                lines.append("_(demək olar ki, istənilən qiymətdə mənfəətlisən)_")
        await send("\n".join(lines))

    # Yekun tövsiyə
    summary = ["🏁 *Yekun tövsiyə*", ""]
    if result["best_now"]:
        best = reports_by_name[result["best_now"]]["now"]
        label = resource_label(result["best_now"], bonus_resources)
        summary.append(f"🏆 İndiki qiymətlərlə ən sərfəli: {label}")
        summary.append(f"({humanize_m(best['net_income_m'])} xalis qazanc)")
        summary.append("")
    if result["best_worst"]:
        best = reports_by_name[result["best_worst"]]["worst"]
        label = resource_label(result["best_worst"], bonus_resources)
        summary.append(f"🔻 Bazar durğunlaşarsa ən sərfəli: {label}")
        summary.append(f"({humanize_m(best['net_income_m'])})")
        summary.append("")
    if result["best_best"]:
        best = reports_by_name[result["best_best"]]["best"]
        label = resource_label(result["best_best"], bonus_resources)
        summary.append(f"🔺 Bazar hərəkətlənərsə ən sərfəli: {label}")
        summary.append(f"({humanize_m(best['net_income_m'])})")
        summary.append("")
    bonus_reports = [reports_by_name[r] for r in bonus_resources if r in reports_by_name and reports_by_name[r].get("has_price")]

    for r in bonus_reports:
        if "alt" in r:
            diff = r["alt"]["diff_net_m"]
            verb = "çox" if diff >= 0 else "az"
            summary.append(f"🎁 Bonuslu {r['name']} fabriki bonussuz olsaydı, {humanize_m(abs(diff))} {verb} qazandırardı.")
            summary.append("")

    if len(bonus_reports) >= 2:
        ranked = sorted(bonus_reports, key=lambda r: r["now"]["net_income_m"], reverse=True)
        summary.append("🎁 *Bonuslu fabriklərin öz aralarında müqayisəsi*")
        summary.append("")
        for i, r in enumerate(ranked, 1):
            summary.append(f"{i}. {r['name']} — {humanize_m(r['now']['net_income_m'])} xalis qazanc")
        summary.append("")
        summary.append(f"👉 Bonuslu fabriklər arasında ən sərfəlisi: {ranked[0]['name']}")

    await send("\n".join(summary))

    restart_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Yenidən başla", callback_data="restart")]])
    if update.callback_query:
        await update.callback_query.message.reply_text("Yenidən hesablamaq istəyirsənsə:", reply_markup=restart_kb)
    else:
        await update.message.reply_text("Yenidən hesablamaq istəyirsənsə:", reply_markup=restart_kb)


# ---------- Geri qayıtma (düzəliş) ----------

async def _reask_health(update, context, prefill):
    context.user_data.pop("health", None)
    await send_numpad_prompt(update, context, "health", "Cari 💊 (sağlıq həbi) balansın neçədir?", prefill=prefill)
    return HEALTH


async def _reask_diamonds(update, context, prefill):
    context.user_data.pop("diamonds", None)
    await send_numpad_prompt(update, context, "diamonds", "Cari 💎 (almaz) balansın neçədir?", prefill=prefill)
    return DIAMONDS


async def _reask_pkg_diamonds(update, context, prefill):
    context.user_data.pop("package_diamonds", None)
    await send_numpad_prompt(update, context, "pkg_diamonds", "Almaz paketində neçə 💎 var? (məs: 50000)", prefill=prefill)
    return PKG_DIAMONDS


async def _reask_pkg_price(update, context, prefill):
    context.user_data.pop("package_price_m", None)
    await send_numpad_prompt(update, context, "pkg_price", "Həmin paketin qiyməti neçə M-dir? (məs: 120M)", prefill=prefill)
    return PKG_PRICE


async def _reask_production(update, context, prefill):
    context.user_data.pop("current_production", None)
    current = context.user_data["current_resource"]
    unit = RESOURCE_UNITS.get(current, "ədəd")
    is_bonus_res = current in context.user_data.get("bonus_resources", set())
    bonus_note = " (bu, bonuslu fabrikindir)" if is_bonus_res else ""
    text = f"{current}{bonus_note} üçün 1 çalışmada nə qədər {unit} istehsal olunur?"
    await send_numpad_prompt(update, context, "production", text, prefill=prefill)
    return COLLECT_PRODUCTION


async def _reask_alt_production(update, context, prefill):
    context.user_data.pop("current_alt_production", None)
    current = context.user_data["current_resource"]
    unit = RESOURCE_UNITS.get(current, "ədəd")
    text = (f"Əgər bonus olmasaydı, 1 çalışmada nə qədər {unit} istehsal edə bilərsən?\n"
            "(bonuslu fabrikin, bonussuz ən yaxşı fabriklə müqayisəsi üçün lazımdır)")
    await send_numpad_prompt(update, context, "alt_production", text, prefill=prefill)
    return COLLECT_ALT_PRODUCTION


async def _reask_bonus_value(update, context, prefill):
    context.user_data.pop("current_bonus_per_work", None)
    text = f"Bonuslu fabrikdə 1 çalışma başına, istehsaldan əlavə, orta hesabla nə qədər ₼ bonus qazanırsan?\n{BIG_NUMBER_HINT}"
    await send_numpad_prompt(update, context, "bonus_value", text, prefill=prefill)
    return BONUS_VALUE


async def _reask_price_now(update, context, prefill):
    context.user_data.pop("current_price_now", None)
    context.user_data["price_step"] = 0
    await send_numpad_prompt(update, context, "price", price_now_prompt_text(context),
                              extra_rows=SKIP_PRICE_ROW, prefill=prefill)
    return COLLECT_PRICE


async def _reask_price_worst(update, context, prefill):
    context.user_data.pop("current_price_worst", None)
    context.user_data["price_step"] = 1
    await send_numpad_prompt(
        update, context, "price",
        "Bazar durğunlaşarsa minimum qiymət nə qədər olar?\n(hesablamaq istəmirsənsə aşağıdakı düyməni bas)",
        extra_rows=SKIP_PRICE_ROW, prefill=prefill,
    )
    return COLLECT_PRICE


REASK_DISPATCH = {
    "health": _reask_health,
    "diamonds": _reask_diamonds,
    "pkg_diamonds": _reask_pkg_diamonds,
    "pkg_price": _reask_pkg_price,
    "production": _reask_production,
    "alt_production": _reask_alt_production,
    "bonus_value": _reask_bonus_value,
    "price_now": _reask_price_now,
    "price_worst": _reask_price_worst,
}


# ---------- Digər ----------

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _clear_numpad_state(context)
    await update.message.reply_text("Ləğv edildi. Yenidən başlamaq üçün /start yaz.", reply_markup=commands_keyboard())
    return ConversationHandler.END


async def fallback_unrecognized(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(
            "⚠️ Bu mesajı başa düşmədim. Zəhmət olmasa yalnız rəqəm daxil et, "
            "ya da /cancel yazıb yenidən /start ilə başla."
        )


HELP_STEPS_TEXT = (
    "📖 *Lazımi məlumatları oyunda necə tapmalı:*\n\n"
    "1️⃣ Baş səhifədən FABRİKLƏR bölməsinə keç.\n"
    "2️⃣ Hər resurs növü üzrə ən yüksək fabrikləri araşdır.\n"
    "3️⃣ Hər 1 çalışmada qazana biləcəyin miqdarı kənara yaz.\n"
    "4️⃣ İş səhifəsindən Bazara keç.\n"
    "5️⃣ Hər resurs üzrə cari qiyməti yaz (qiymət tendensiyasını izləmək faydalıdır).\n\n"
    "Bu rəqəmləri topladıqdan sonra /start yazıb hesablamaya başlaya bilərsən."
)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_url = context.application.bot_data.get("help_url")
    if help_url:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("📖 Şəkilli təlimatı aç", url=help_url)]])
        await update.message.reply_text(
            "Aşağıdakı düymədən şəkilli təlimatı aça bilərsən, ya da qısa xülasəni burada oxu:",
            reply_markup=kb,
        )
    await update.message.reply_text(HELP_STEPS_TEXT, parse_mode="Markdown")


async def qiymetler_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = ["📈 *İcma bazar qiymətləri* (istifadəçilərin bildirdiyi son dəyərlər)\n"]
    any_data = False
    for r in RESOURCE_ORDER:
        stats = price_history.get_stats(context.bot_data, r)
        if stats:
            any_data = True
        lines.append(price_history.format_summary_line(r, stats))
    if not any_data:
        lines.append("\n_Hələ heç kim qiymət bildirməyib. Hesablama zamanı daxil etdiyin qiymətlər "
                      "avtomatik (anonim) əlavə olunur._")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def post_init(app):
    await app.bot.set_my_commands([
        BotCommand("start", "🚀 Hesablamanı başlat"),
        BotCommand("help", "❓ Necə etməli? (təlimat)"),
        BotCommand("qiymetler", "📈 İcma bazar qiymətləri"),
        BotCommand("cancel", "❌ Cari hesablamanı ləğv et"),
    ])
    await app.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    help_url = await asyncio.to_thread(telegraph_setup.get_or_create_help_url)
    app.bot_data["help_url"] = help_url


# Rəqəm klaviaturasının "✅" (təsdiqlə) düyməsi hansı funksiyanı çağıracaq.
# Bütün funksiyalar artıq həm mesaj, həm də klaviatura vasitəsilə çağırıla bilər
# (raw_text verilməzsə update.message.text-dən oxuyur).
STEP_HANDLER = {
    "health": health,
    "diamonds": diamonds,
    "pkg_diamonds": pkg_diamonds,
    "pkg_price": pkg_price,
    "production": collect_production,
    "alt_production": collect_alt_production,
    "bonus_value": bonus_value,
    "price": collect_price,
}


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN mühit dəyişəni tapılmadı.")

    persistence = PicklePersistence(filepath=os.environ.get("BOT_PERSISTENCE_PATH", "bot_persistence.pkl"))
    app = ApplicationBuilder().token(token).persistence(persistence).post_init(post_init).build()

    # "🚀 Başla" və "❌ Ləğv et" söhbətin gedişatını dəyişdiyi üçün (yeni state-ə
    # keçir/bitirir) hər state-in öz siyahısına əlavə olunur - bununla
    # ConversationHandler-in daxili "hansı state-dəyəm" izləməsi düzgün qalır.
    RESTART_SHORTCUT = MessageHandler(filters.Text([BUTTON_START]), start)
    CANCEL_SHORTCUT = MessageHandler(filters.Text([BUTTON_CANCEL]), cancel)
    SHORTCUTS = [RESTART_SHORTCUT, CANCEL_SHORTCUT]

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(start, pattern="^restart$"),
            RESTART_SHORTCUT,
        ],
        states={
            MODE: [CallbackQueryHandler(mode_choice, pattern="^mode_"), *SHORTCUTS],
            HEALTH: [
                CallbackQueryHandler(numpad_callback, pattern="^np_"),
                *SHORTCUTS,
                MessageHandler(filters.TEXT & ~filters.COMMAND, health),
            ],
            DIAMONDS: [
                CallbackQueryHandler(numpad_callback, pattern="^np_"),
                *SHORTCUTS,
                MessageHandler(filters.TEXT & ~filters.COMMAND, diamonds),
            ],
            PKG_DIAMONDS: [
                CallbackQueryHandler(numpad_callback, pattern="^np_"),
                *SHORTCUTS,
                MessageHandler(filters.TEXT & ~filters.COMMAND, pkg_diamonds),
            ],
            PKG_PRICE: [
                CallbackQueryHandler(numpad_callback, pattern="^np_"),
                *SHORTCUTS,
                MessageHandler(filters.TEXT & ~filters.COMMAND, pkg_price),
            ],
            RESOURCE_SELECT: [CallbackQueryHandler(resource_toggle, pattern="^res_"), *SHORTCUTS],
            BONUS_YN: [CallbackQueryHandler(bonus_yn, pattern="^bonus_"), *SHORTCUTS],
            BONUS_RESOURCE: [CallbackQueryHandler(bonus_resource_toggle, pattern="^bonusres_"), *SHORTCUTS],
            COLLECT_PRODUCTION: [
                CallbackQueryHandler(use_saved_production_callback, pattern="^useprod_production$"),
                CallbackQueryHandler(numpad_callback, pattern="^np_"),
                *SHORTCUTS,
                MessageHandler(filters.TEXT & ~filters.COMMAND, collect_production),
            ],
            COLLECT_ALT_PRODUCTION: [
                CallbackQueryHandler(use_saved_production_callback, pattern="^useprod_alt_production$"),
                CallbackQueryHandler(numpad_callback, pattern="^np_"),
                *SHORTCUTS,
                MessageHandler(filters.TEXT & ~filters.COMMAND, collect_alt_production),
            ],
            BONUS_VALUE: [
                CallbackQueryHandler(numpad_callback, pattern="^np_"),
                *SHORTCUTS,
                MessageHandler(filters.TEXT & ~filters.COMMAND, bonus_value),
            ],
            COLLECT_PRICE: [
                CallbackQueryHandler(numpad_callback, pattern="^np_"),
                CallbackQueryHandler(skip_price_callback, pattern="^skip_price$"),
                *SHORTCUTS,
                MessageHandler(filters.TEXT & ~filters.COMMAND, collect_price),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            *SHORTCUTS,
            MessageHandler(filters.ALL, fallback_unrecognized),
        ],
        allow_reentry=True,
        name="main_conversation",
        persistent=True,
    )

    # "❓ Kömək" və "📈 Qiymətlər" söhbətin state-ini dəyişmir (sadəcə məlumat
    # göstərir), ona görə ConversationHandler-dən ƏVVƏL, qlobal səviyyədə
    # qeydə alınır - /help kimi, hansı state-də olur-olsun işləyir və
    # söhbətin gedişatına toxunmur.
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.Text([BUTTON_HELP]), help_command))
    app.add_handler(CommandHandler("qiymetler", qiymetler_command))
    app.add_handler(MessageHandler(filters.Text([BUTTON_QIYMETLER]), qiymetler_command))
    app.add_handler(conv)
    app.run_polling()


if __name__ == "__main__":
    main()
