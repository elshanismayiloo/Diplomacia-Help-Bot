# -*- coding: utf-8 -*-
"""
Diplomacia Profit Calculator - Telegram Bot

İşə salmaq üçün:
1. pip install -r requirements.txt
2. export TELEGRAM_BOT_TOKEN="sizin_token"
3. python bot.py
"""

import os
import logging
from telegram import (
    Update, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand,
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ConversationHandler,
    MessageHandler, CallbackQueryHandler, ContextTypes, filters
)

from calculator import (
    GameInput, ResourceInput, full_analysis, order_resources, format_duration,
    humanize_m, humanize_number, format_price,
    try_parse_money, try_parse_package_price, RESOURCE_UNITS, RESOURCE_ORDER, MARKET_BATCH_SIZE,
)

logging.basicConfig(level=logging.INFO)

(MODE, HEALTH, DIAMONDS, PKG_DIAMONDS, PKG_PRICE,
 RESOURCE_SELECT, BONUS_YN, BONUS_RESOURCE,
 COLLECT_PRODUCTION, COLLECT_ALT_PRODUCTION, COLLECT_PRICE) = range(11)

BIG_NUMBER_HINT = "(rəqəmi istənilən formatda yaza bilərsən: 50000, 50k, 1m, 1M, 1kkk)"
SKIP_PRICE_KB = InlineKeyboardMarkup([[InlineKeyboardButton("⏭ Hesablamaq istəmirəm", callback_data="skip_price")]])


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


def bonus_resource_keyboard(options):
    return InlineKeyboardMarkup([[InlineKeyboardButton(r, callback_data=f"bonusres_{r}") for r in options]])


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


def resource_label(name: str, bonus_resource_name):
    return f"bonuslu {name}" if name == bonus_resource_name else name


# ---------- Başlanğıc ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    text = (
        "Salam! Diplomacia gəlir hesablayıcısına xoş gəldin.\n\n"
        lines.append("İstənilən vaxt /cancel ilə dayandıra bilərsən.\n")
        lines.append(f"Böyük rəqəm tələb olunan suallarda istənilən formatda yaza bilərsən: \n")
        f"50000, 50k, 1m, 1M, 1kkk.\n\n"
        lines.append("Necə hesablamaq istəyirsən?")
    )
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(text, reply_markup=mode_keyboard())
    else:
        await update.message.reply_text(text, reply_markup=ReplyKeyboardRemove())
        await update.message.reply_text("Seçim et:", reply_markup=mode_keyboard())
    return MODE


async def mode_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["use_existing_balance"] = (query.data == "mode_balance")
    await query.edit_message_text("Cari 💊 (sağlıq həbi) balansın neçədir?")
    return HEALTH


# ---------- Balans ----------

async def health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = try_parse_money(update.message.text)
    if value is None:
        await update.message.reply_text("⚠️ Rəqəm kimi tanınmadı. Zəhmət olmasa yenidən yaz (məs: 50000 və ya 50k).")
        return HEALTH
    context.user_data["health"] = value
    await update.message.reply_text("Cari 💎 (almaz) balansın neçədir?")
    return DIAMODS


async def diamonds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = try_parse_money(update.message.text)
    if value is None:
        await update.message.reply_text("⚠️ Rəqəm kimi tanınmadı. Zəhmət olmasa yenidən yaz (məs: 40000 və ya 40k).")
        return DIAMONDS
    context.user_data["diamonds"] = value
    if context.user_data.get("use_existing_balance"):
        return await ask_resource_select(update, context, from_callback=False)
    await update.message.reply_text("Almaz paketində neçə 💎 var? (məs: 50000 və ya 50k)")
    return PKG_DIAMONDS


async def pkg_diamonds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = try_parse_money(update.message.text)
    if value is None:
        await update.message.reply_text("⚠️ Rəqəm kimi tanınmadı. Zəhmət olmasa yenidən yaz (məs: 50000 və ya 50k).")
        return PKG_DIAMONDS
    context.user_data["package_diamonds"] = value
    await update.message.reply_text("Həmin paketin qiyməti neçə M-dir? (məs: 120 və ya 120M)")
    return PKG_PRICE


async def pkg_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = try_parse_package_price(update.message.text)
    if value is None:
        await update.message.reply_text("⚠️ Rəqəm kimi tanınmadı. Zəhmət olmasa yenidən yaz (məs: 120 və ya 120M).")
        return PKG_PRICE
    context.user_data["package_price_m"] = value
    return await ask_resource_select(update, context, from_callback=False)


# ---------- Resurs seçimi ----------

async def ask_resource_select(update: Update, context: ContextTypes.DEFAULT_TYPE, from_callback: bool):
    context.user_data["selected"] = set()
    text = "Hansı resurs(lar) üçün hesablamaq istəyirsən?"
    kb_text = "Bir və ya bir neçə resurs seç, sonra 'Davam et' düyməsinə bas:"
    if from_callback:
        await update.callback_query.edit_message_text(text)
        await update.callback_query.message.reply_text(kb_text, reply_markup=resource_select_keyboard(set()))
    else:
        await update.message.reply_text(text)
        await update.message.reply_text(kb_text, reply_markup=resource_select_keyboard(set()))
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
        await query.message.reply_text("Bonuslu fabrik var?", reply_markup=bonus_yn_keyboard())
        return BONUS_YN
    else:
        r = query.data.replace("res_toggle_", "")
        if r in selected:
            selected.discard(r)
        else:
            selected.add(r)

    await query.edit_message_reply_markup(reply_markup=resource_select_keyboard(selected))
    return RESOURCE_SELECT


# ---------- Bonus ----------

async def bonus_yn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "bonus_yes":
        context.user_data["bonus_active"] = True
        options = context.user_data["ordered_selected"]
        await query.edit_message_text("Bonuslu fabrik hansı resurs üzrədir?", reply_markup=bonus_resource_keyboard(options))
        return BONUS_RESOURCE
    else:
        context.user_data["bonus_active"] = False
        context.user_data["bonus_resource"] = None
        return await start_resource_queue(update, context)


async def bonus_resource(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    resource = query.data.replace("bonusres_", "")
    context.user_data["bonus_resource"] = resource
    await query.edit_message_text(f"Bonuslu fabrik: {resource}")
    return await start_resource_queue(update, context)


async def start_resource_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["queue"] = list(context.user_data["ordered_selected"])
    context.user_data["finished_resources"] = []
    return await ask_next_production(update, context)


# ---------- Resurs məlumatları (istehsal + qiymətlər) ----------

async def ask_next_production(update: Update, context: ContextTypes.DEFAULT_TYPE):
    queue = context.user_data["queue"]
    current = queue[0]
    context.user_data["current_resource"] = current
    context.user_data["price_step"] = 0
    unit = RESOURCE_UNITS.get(current, "ədəd")
    is_bonus_res = context.user_data.get("bonus_active") and context.user_data.get("bonus_resource") == current
    bonus_note = " (bu, bonuslu fabrikindir)" if is_bonus_res else ""
    text = f"{current}{bonus_note} üçün 1 çalışmada nə qədər {unit} istehsal olunur?"
    if update.callback_query:
        await update.callback_query.message.reply_text(text)
    else:
        await update.message.reply_text(text)
    return COLLECT_PRODUCTION


async def collect_production(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = try_parse_money(update.message.text)
    if value is None:
        await update.message.reply_text("⚠️ Rəqəm kimi tanınmadı. Zəhmət olmasa yenidən yaz.")
        return COLLECT_PRODUCTION
    context.user_data["current_production"] = value

    current = context.user_data["current_resource"]
    is_bonus_res = context.user_data.get("bonus_active") and context.user_data.get("bonus_resource") == current
    if is_bonus_res:
        unit = RESOURCE_UNITS.get(current, "ədəd")
        await update.message.reply_text(
            f"Əgər bonuslu fabrik olmasaydı, 1 çalışmada ən çox nə qədər {unit} istehsal olunardı?\n"
            "(bonuslu fabrikin, bonussuz ən yaxşı fabriklə müqayisəsi üçün lazımdır)"
        )
        return COLLECT_ALT_PRODUCTION

    context.user_data["price_step"] = 0
    await update.message.reply_text(
        "İndiki bazar qiyməti neçədir?\n"
        lines.append("(bu resurs üçün gəlir hesablamaq istəmirsənsə, aşağıdakı düyməni basa bilərsən)"),
        reply_markup=SKIP_PRICE_KB,
    )
    return COLLECT_PRICE


async def collect_alt_production(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = try_parse_money(update.message.text)
    if value is None:
        await update.message.reply_text("⚠️ Rəqəm kimi tanınmadı. Zəhmət olmasa yenidən yaz.")
        return COLLECT_ALT_PRODUCTION
    context.user_data["current_alt_production"] = value
    context.user_data["price_step"] = 0
    await update.message.reply_text(
        "İndiki bazar qiyməti neçədir?\n"
        lines.append("(bu resurs üçün gəlir hesablamaq istəmirsənsə, aşağıdakı düyməni basa bilərsən)"),
        reply_markup=SKIP_PRICE_KB,
    )
    return COLLECT_PRICE


async def _handle_price_value(update: Update, context: ContextTypes.DEFAULT_TYPE, value: float, reply_text):
    step = context.user_data.get("price_step", 0)

    if step == 0:
        if value == 0:
            context.user_data["current_price_now"] = None
            return await finish_current_resource(update, context)
        context.user_data["current_price_now"] = value
        context.user_data["price_step"] = 1
        await reply_text(
            "Bazar durğunlaşarsa minimum qiymət nə qədər olar?\n"
            lines.append("(bu resurs üçün gəlir hesablamaq istəmirsənsə, aşağıdakı düyməni basa bilərsən)"),
            reply_markup=SKIP_PRICE_KB,
        )
        return COLLECT_PRICE

    if step == 1:
        context.user_data["current_price_worst"] = None if value == 0 else value
        context.user_data["price_step"] = 2
        await reply_text(
            "Bazar hərəkətlənərsə maksimum qiymət nə qədər olar?\n"
            lines.append("(bu resurs üçün gəlir hesablamaq istəmirsənsə, aşağıdakı düyməni basa bilərsən)"),
            reply_markup=SKIP_PRICE_KB,
        )
        return COLLECT_PRICE

    context.user_data["current_price_best"] = None if value == 0 else value
    return await finish_current_resource(update, context)


async def collect_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = try_parse_money(update.message.text)
    if value is None:
        await update.message.reply_text("⚠️ Rəqəm kimi tanınmadı. Zəhmət olmasa yenidən yaz (0 = keç).")
        return COLLECT_PRICE
    return await _handle_price_value(update, context, value, update.message.reply_text)


async def skip_price_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    async def reply_text(text, reply_markup=None):
        await query.message.reply_text(text, reply_markup=reply_markup)

    return await _handle_price_value(update, context, 0.0, reply_text)


async def finish_current_resource(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ud = context.user_data
    resource = ResourceInput(
        name=ud["current_resource"],
        production_per_work=ud["current_production"],
        price_now=ud.get("current_price_now"),
        price_worst=ud.get("current_price_worst"),
        price_best=ud.get("current_price_best"),
        alt_production_per_work=ud.get("current_alt_production"),
    )
    ud["finished_resources"].append(resource)
    ud["queue"].pop(0)

    for k in ("current_resource", "current_production", "current_price_now",
              "current_price_worst", "current_price_best", "current_alt_production", "price_step"):
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
        bonus_active=ud.get("bonus_active", False),
        bonus_resource_name=ud.get("bonus_resource"),
        resources=ud["finished_resources"],
    )

    result = full_analysis(game_input)
    reports_by_name = {r["name"]: r for r in result["reports"]}
    cost_per_work = result["cost_per_work_m"]
    bonus_resource_name = game_input.bonus_resource_name if game_input.bonus_active else None

    async def send(text):
        if update.callback_query:
            await update.callback_query.message.reply_text(text, parse_mode="Markdown")
        else:
            await update.message.reply_text(text, parse_mode="Markdown")

    header_lines = [
        "📊 *Nəticələr*",
        f"Çalışma sayı: *{humanize_number(result['total_works'])}*",
        f"Təxmini vaxt: *{format_duration(result['total_duration_seconds'])}*",
    ]
    if cost_per_work > 0:
        header_lines.append(f"1 çalışmanın maya dəyəri: *{humanize_m(cost_per_work)}*")
    else:
        header_lines.append("_Mövcud balansla hesablanır (maya dəyəri tətbiq olunmur)_")
    await send("\n".join(header_lines))

    for r in result["reports"]:
        unit = RESOURCE_UNITS.get(r["name"], "ədəd")
        label = resource_label(r["name"], bonus_resource_name)
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
                lines.append(f"(bonus sənə {humanize_m(diff)} ₼ əlavə qazandırır)")
            else:
                lines.append(f"⚠️ Bonus olmasaydı: {humanize_m(alt['now']['net_income_m'])}")
                lines.append(f"(bonus əslində {humanize_m(abs(diff))} ₼ qazandırır - istehsal fərqinə görə)")
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
        label = resource_label(result["best_now"], bonus_resource_name)
        summary.append(f"🏆 İndiki qiymətlərlə ən sərfəli: {label}")
        summary.append(f"({humanize_m(best['net_income_m'])} xalis qazanc)")
        summary.append("")
    if result["best_worst"]:
        best = reports_by_name[result["best_worst"]]["worst"]
        label = resource_label(result["best_worst"], bonus_resource_name)
        summary.append(f"🔻 Bazar durğunlaşarsa ən sərfəli: {label}")
        summary.append(f"({humanize_m(best['net_income_m'])})")
        summary.append("")
    if result["best_best"]:
        best = reports_by_name[result["best_best"]]["best"]
        label = resource_label(result["best_best"], bonus_resource_name)
        summary.append(f"🔺 Bazar hərəkətlənərsə ən sərfəli: {label}")
        summary.append(f"({humanize_m(best['net_income_m'])})")
        summary.append("")

    if bonus_resource_name and bonus_resource_name in reports_by_name:
        bonus_rep = reports_by_name[bonus_resource_name]
        if "alt" in bonus_rep:
            diff = bonus_rep["alt"]["diff_net_m"]
            if diff >= 0:
                summary.append(f"Bonuslu {bonus_resource_name} fabriki")
                summary.append(f"ən yaxşı adi {bonus_resource_name} fabrikindən")
                summary.append(f"{humanize_m(diff)} ₼ çox qazandırır.")
            else:
                summary.append(f"Bonuslu {bonus_resource_name} fabriki")
                summary.append(f"ən yaxşı adi {bonus_resource_name} fabrikindən")
                summary.append(f"{humanize_m(abs(diff))} ₼ qazandırır.")

    await send("\n".join(summary))

    restart_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Yenidən başla", callback_data="restart")]])
    if update.callback_query:
        await update.callback_query.message.reply_text("Yenidən hesablamaq istəyirsənsə:", reply_markup=restart_kb)
    else:
        await update.message.reply_text("Yenidən hesablamaq istəyirsənsə:", reply_markup=restart_kb)


# ---------- Digər ----------

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ləğv edildi. Yenidən başlamaq üçün /start yaz.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


async def fallback_unrecognized(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(
            "⚠️ Bu mesajı başa düşmədim. Zəhmət olmasa yalnız rəqəm daxil et, "
            "ya da /cancel yazıb yenidən /start ilə başla."
        )


async def post_init(app):
    await app.bot.set_my_commands([
        BotCommand("start", "Hesablamanı başlat"),
        BotCommand("cancel", "Cari hesablamanı ləğv et"),
    ])


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN mühit dəyişəni tapılmadı.")

    app = ApplicationBuilder().token(token).post_init(post_init).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(start, pattern="^restart$"),
        ],
        states={
            MODE: [CallbackQueryHandler(mode_choice, pattern="^mode_")],
            HEALTH: [MessageHandler(filters.TEXT & ~filters.COMMAND, health)],
            DIAMONDS: [MessageHandler(filters.TEXT & ~filters.COMMAND, diamonds)],
            PKG_DIAMONDS: [MessageHandler(filters.TEXT & ~filters.COMMAND, pkg_diamonds)],
            PKG_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, pkg_price)],
            RESOURCE_SELECT: [CallbackQueryHandler(resource_toggle, pattern="^res_")],
            BONUS_YN: [CallbackQueryHandler(bonus_yn, pattern="^bonus_")],
            BONUS_RESOURCE: [CallbackQueryHandler(bonus_resource, pattern="^bonusres_")],
            COLLECT_PRODUCTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_production)],
            COLLECT_ALT_PRODUCTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_alt_production)],
            COLLECT_PRICE: [
                CallbackQueryHandler(skip_price_callback, pattern="^skip_price$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, collect_price),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            MessageHandler(filters.ALL, fallback_unrecognized),
        ],
    )

    app.add_handler(conv)
    app.run_polling()


if __name__ == "__main__":
    main()
