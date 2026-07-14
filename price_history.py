# -*- coding: utf-8 -*-
"""
Qiymət tarixçəsi - istifadəçilərin daxil etdiyi "indiki bazar qiyməti"
dəyərlərini anonim şəkildə bot_data-da toplayır (heç bir istifadəçi ID-si
saxlanmır, yalnız rəqəm + vaxt). Bu, botun mövcud PicklePersistence
mexanizmi ilə avtomatik saxlanır/bərpa olunur.

Məqsəd: istifadəçilər "İndiki bazar qiyməti neçədir?" sualına cavab verəndə,
icmanın son vaxtlar bildirdiyi qiymətləri və tendensiyanı görə bilsinlər.
"""

import time

HISTORY_KEY = "price_history"
KEEP_DAYS = 30
MAX_ENTRIES_PER_RESOURCE = 500


def record_price(bot_data: dict, resource: str, price: float):
    """Anonim şəkildə yeni qiymət qeydi əlavə edir və köhnə/artıq qeydləri təmizləyir."""
    if price is None or price <= 0:
        return
    history = bot_data.setdefault(HISTORY_KEY, {})
    entries = history.setdefault(resource, [])
    entries.append({"price": price, "ts": time.time()})
    cutoff = time.time() - KEEP_DAYS * 86400
    entries[:] = [e for e in entries if e["ts"] >= cutoff][-MAX_ENTRIES_PER_RESOURCE:]


def _avg(entries):
    return sum(e["price"] for e in entries) / len(entries) if entries else None


def get_stats(bot_data: dict, resource: str):
    """Resurs üzrə icma statistikasını qaytarır, məlumat yoxdursa None."""
    entries = bot_data.get(HISTORY_KEY, {}).get(resource, [])
    if not entries:
        return None
    now = time.time()
    last_24h = [e for e in entries if now - e["ts"] <= 86400]
    last_7d = [e for e in entries if now - e["ts"] <= 7 * 86400]
    latest = entries[-1]
    avg_24h = _avg(last_24h)
    avg_7d = _avg(last_7d)
    trend_percent = None
    if avg_24h is not None and avg_7d and avg_7d > 0:
        trend_percent = (avg_24h - avg_7d) / avg_7d * 100
    return {
        "latest_price": latest["price"],
        "latest_age_seconds": now - latest["ts"],
        "avg_24h": avg_24h,
        "count_24h": len(last_24h),
        "avg_7d": avg_7d,
        "count_7d": len(last_7d),
        "trend_percent": trend_percent,
        "total_count": len(entries),
    }


def _age_text(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 3600:
        return f"{max(1, seconds // 60)} dəq əvvəl"
    if seconds < 86400:
        return f"{seconds // 3600} saat əvvəl"
    return f"{seconds // 86400} gün əvvəl"


def trend_arrow(trend_percent):
    if trend_percent is None:
        return "➡️"
    if trend_percent > 2:
        return "📈"
    if trend_percent < -2:
        return "📉"
    return "➡️"


def format_inline_hint(resource: str, stats: dict) -> str:
    """Qiymət sualına əlavə olunan qısa icma məlumatı sətri."""
    if not stats:
        return ""
    lines = [f"💡 İcma məlumatı ({resource}): son qeyd {stats['latest_price']:,.2f} "
              f"({_age_text(stats['latest_age_seconds'])})"]
    if stats["avg_24h"] is not None and stats["count_24h"] >= 2:
        arrow = trend_arrow(stats["trend_percent"])
        trend_text = f", {arrow} {stats['trend_percent']:+.1f}% (7 günlə müq.)" if stats["trend_percent"] is not None else ""
        lines.append(f"   24 saatlıq orta: {stats['avg_24h']:,.2f} ({stats['count_24h']} bildiriş){trend_text}")
    return "\n".join(lines)


def format_summary_line(resource: str, stats: dict) -> str:
    """/qiymetler əmri üçün hər resurs üzrə bir sətirlik xülasə."""
    if not stats:
        return f"{resource}  —  hələ məlumat yoxdur"
    arrow = trend_arrow(stats["trend_percent"])
    trend_text = f" {arrow} {stats['trend_percent']:+.1f}%" if stats["trend_percent"] is not None else ""
    return (f"{resource}  son: {stats['latest_price']:,.2f} ({_age_text(stats['latest_age_seconds'])})"
            f" | 24s orta: {stats['avg_24h']:,.2f}{trend_text}" if stats["avg_24h"] is not None
            else f"{resource}  son: {stats['latest_price']:,.2f} ({_age_text(stats['latest_age_seconds'])})")
