# -*- coding: utf-8 -*-
"""
Diplomacia Profit Calculator - Telegram Bot

İşə salmaq üçün:
1. pip install -r requirements.txt
2. Terminalda: export TELEGRAM_BOT_TOKEN="sizin_token"   (Windows: set TELEGRAM_BOT_TOKEN=...)
3. python bot.py

Hər istifadəçi botla ayrıca, məxfi (private) söhbətdə danışır -
onların cavabları başqalarına görünmür.
"""

import os
import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ConversationHandler,
    MessageHandler, ContextTypes, filters
)

from calculator import GameInput, ResourceInput, full_analysis

logging.basicConfig(level=logging.INFO)

(HEALTH, DIAMONDS, PKG_DIAMONDS, PKG_PRICE, BONUS_YN, BONUS_RESOURCE, BONUS_M,
 PROD_DEER, PROD_COIN, PROD_OIL, PROD_POTION,
 PRICE_DEER, PRICE_COIN, PRICE_OIL, PRICE_POTION) = range(15)

RESOURCE_NAMES = ["🦌", "🪙", "🛢", "⚗️"]


def parse_prices(text: str):
    """'50' və ya '45,60' (worst,best) və ya '50 45 60' formatlarını qəbul edir."""
    parts = [p.strip() for p in text.replace(",", " ").split() if p.strip()]
    nums = [float(p) for p in parts]
    now = nums[0]
    worst = nums[1] if len(nums) > 1 else None
    best = nums[2] if len(nums) > 2 else None
    return now, worst, best


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Salam! Diplomacia mənfəət kalkulyatoruna xoş gəldiniz.\n\n"
        "Sizə bir neçə sual verəcəyəm. İstənilən vaxt /cancel ilə dayandıra bilərsiniz.\n\n"
        "Cari 💊 (enerji) balansınız neçədir?",
        reply_markup=ReplyKeyboardRemove(),
    )
    return HEALTH


async def health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["health"] = float(update.message.text.strip())
    await update.message.reply_text("Cari 💎 (almaz) balansınız neçədir?")
    return DIAMONDS


async def diamonds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["diamonds"] = float(update.message.text.strip())
    await update.message.reply_text(
        "Almaz paketində neçə 💎 var? (məs: 50000)"
    )
    return PKG_DIAMONDS


async def pkg_diamonds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["package_diamonds"] = float(update.message.text.strip())
    await update.message.reply_text("Həmin paketin qiyməti neçə M-dir? (məs: 120)")
    return PKG_PRICE


async def pkg_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["package_price_m"] = float(update.message.text.strip())
    kb = ReplyKeyboardMarkup([["Bəli", "Xeyr"]], one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("Bonuslu fabrikiniz var mı?", reply_markup=kb)
    return BONUS_YN


async def bonus_yn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ans = update.message.text.strip().lower()
    if ans.startswith("b"):
        context.user_data["bonus_active"] = True
        kb = ReplyKeyboardMarkup([RESOURCE_NAMES], one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(
            "Bonuslu fabrik hansı resurs üzrədir?", reply_markup=kb
        )
        return BONUS_RESOURCE
    else:
        context.user_data["bonus_active"] = False
        context.user_data["bonus_resource"] = None
        context.user_data["bonus_m_per_50"] = 0.0
        await update.message.reply_text(
            "🦌 üçün 1 çalışmada nə qədər istehsal olunur?",
            reply_markup=ReplyKeyboardRemove(),
        )
        return PROD_DEER


async def bonus_resource(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["bonus_resource"] = update.message.text.strip()
    await update.message.reply_text(
        "Hər 50 çalışma üçün əlavə bonus neçə M-dir?", reply_markup=ReplyKeyboardRemove()
    )
    return BONUS_M


async def bonus_m(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["bonus_m_per_50"] = float(update.message.text.strip())
    await update.message.reply_text("🦌 üçün 1 çalışmada nə qədər istehsal olunur? (bonuslu fabrikdəki miqdarı yazın)")
    return PROD_DEER


async def prod_deer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["prod_deer"] = float(update.message.text.strip())
    await update.message.reply_text("🪙 üçün 1 çalışmada nə qədər istehsal olunur?")
    return PROD_COIN


async def prod_coin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["prod_coin"] = float(update.message.text.strip())
    await update.message.reply_text("🛢 üçün 1 çalışmada nə qədər istehsal olunur?")
    return PROD_OIL


async def prod_oil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["prod_oil"] = float(update.message.text.strip())
    await update.message.reply_text("⚗️ üçün 1 çalışmada nə qədər istehsal olunur?")
    return PROD_POTION


async def prod_potion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["prod_potion"] = float(update.message.text.strip())
    await update.message.reply_text(
        "🦌 qiyməti(-ləri) M-lə: yalnız indiki qiymət, ya da 'indiki,pis,yaxşı' "
        "formatında (məs: 31  və ya  31,25,40)"
    )
    return PRICE_DEER


async def price_deer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["price_deer"] = parse_prices(update.message.text)
    await update.message.reply_text("🪙 qiyməti(-ləri)?")
    return PRICE_COIN


async def price_coin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["price_coin"] = parse_prices(update.message.text)
    await update.message.reply_text("🛢 qiyməti(-ləri)?")
    return PRICE_OIL


async def price_oil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["price_oil"] = parse_prices(update.message.text)
    await update.message.reply_text("⚗️ qiyməti(-ləri)?")
    return PRICE_POTION


async def price_potion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["price_potion"] = parse_prices(update.message.text)
    await compute_and_send(update, context)
    return ConversationHandler.END


async def compute_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ud = context.user_data
    bonus_resource_name = ud.get("bonus_resource")

    resources = []
    prod_map = {
        "🦌": ud["prod_deer"], "🪙": ud["prod_coin"],
        "🛢": ud["prod_oil"], "⚗️": ud["prod_potion"],
    }
    price_map = {
        "🦌": ud["price_deer"], "🪙": ud["price_coin"],
        "🛢": ud["price_oil"], "⚗️": ud["price_potion"],
    }
    for name in RESOURCE_NAMES:
        now, worst, best = price_map[name]
        resources.append(ResourceInput(
            name=name,
            production_per_work=prod_map[name],
            price_now=now, price_worst=worst, price_best=best,
            is_bonus_factory=(name == bonus_resource_name),
        ))

    game_input = GameInput(
        health=ud["health"], diamonds=ud["diamonds"],
        package_diamonds=ud["package_diamonds"], package_price_m=ud["package_price_m"],
        bonus_active=ud["bonus_active"], bonus_m_per_50_works=ud.get("bonus_m_per_50", 0.0),
        resources=resources,
    )

    result = full_analysis(game_input)

    lines = [
        f"📊 *Nəticələr*",
        f"Toplam mümkün çalışma: *{result['total_works']}*",
        f"1 çalışmanın maya dəyəri: *{result['cost_per_work_m']} M*",
        "",
    ]
    for r in result["reports"]:
        lines.append(f"*{r['name']}*")
        n = r["now"]
        lines.append(f"  İndiki: istehsal={n['production']}, gəlir={n['revenue_m']}M, "
                      f"xərc={n['total_cost_m']}M, xalis={n['net_profit_m']}M, ROI={n['roi_percent']}%")
        if "worst" in r:
            w = r["worst"]
            lines.append(f"  Pis ssenari: xalis={w['net_profit_m']}M, ROI={w['roi_percent']}%")
        if "best" in r:
            b = r["best"]
            lines.append(f"  Yaxşı ssenari: xalis={b['net_profit_m']}M, ROI={b['roi_percent']}%")
        lines.append(f"  Break-even qiymət: {r['break_even_price']}")
        lines.append("")

    lines.append(f"🏆 Ən sərfəli (indiki qiymətlərlə): *{result['best_now']}*")
    if result["best_worst"]:
        lines.append(f"🔻 Ən sərfəli (pis ssenari): *{result['best_worst']}*")
    if result["best_best"]:
        lines.append(f"🔺 Ən sərfəli (yaxşı ssenari): *{result['best_best']}*")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ləğv edildi.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN mühit dəyişəni tapılmadı.")

    app = ApplicationBuilder().token(token).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            HEALTH: [MessageHandler(filters.TEXT & ~filters.COMMAND, health)],
            DIAMONDS: [MessageHandler(filters.TEXT & ~filters.COMMAND, diamonds)],
            PKG_DIAMONDS: [MessageHandler(filters.TEXT & ~filters.COMMAND, pkg_diamonds)],
            PKG_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, pkg_price)],
            BONUS_YN: [MessageHandler(filters.TEXT & ~filters.COMMAND, bonus_yn)],
            BONUS_RESOURCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, bonus_resource)],
            BONUS_M: [MessageHandler(filters.TEXT & ~filters.COMMAND, bonus_m)],
            PROD_DEER: [MessageHandler(filters.TEXT & ~filters.COMMAND, prod_deer)],
            PROD_COIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, prod_coin)],
            PROD_OIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, prod_oil)],
            PROD_POTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, prod_potion)],
            PRICE_DEER: [MessageHandler(filters.TEXT & ~filters.COMMAND, price_deer)],
            PRICE_COIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, price_coin)],
            PRICE_OIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, price_oil)],
            PRICE_POTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, price_potion)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv)
    app.run_polling()


if __name__ == "__main__":
    main()
