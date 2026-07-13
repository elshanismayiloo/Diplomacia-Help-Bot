# -*- coding: utf-8 -*-
"""
Diplomacia Profit Calculator - hesablama məntiqi.

Oyun mexanikası:
- 1 çalışma = 100 enerji (sağlıq həbi), bunun 5-i pulsuz regenerasiya olunur
  -> faktiki xərc 95 sağlıq həbi (💊).
- 💊 -> 💎 nisbəti: 5 💊 = 1 💎 (yəni 95 💊 = 19 💎).
- Hər 10 dəqiqədə 1 dəfə çalışmaq mümkündür (sabit interval).
- Almaz paketi: X 💎 = Y M. Paket qiymətləri adətən milyonlarladır - "120"
  yazsan, bu, avtomatik 120 milyon kimi qəbul olunur.
- Bazarda 1 dəfəyə maksimum 20 000 ədəd/barrel satıla bilər.
"""

import math
from dataclasses import dataclass, field
from typing import Optional

ENERGY_PER_WORK = 100
FREE_REGEN_PER_WORK = 5
NET_ENERGY_COST = ENERGY_PER_WORK - FREE_REGEN_PER_WORK  # 95
HEALTH_TO_DIAMOND_RATE = 5  # 5 💊 = 1 💎
MARKET_BATCH_SIZE = 20000  # bazarda 1 dəfəyə satıla bilən maksimum miqdar
WORK_INTERVAL_SECONDS = 600  # hər 10 dəqiqədə 1 çalışma

RESOURCE_ORDER = ["🦌", "🪙", "🛢", "⚗️"]
RESOURCE_UNITS = {
    "🦌": "ədəd",
    "🪙": "ədəd",
    "🛢": "barrel",
    "⚗️": "ədəd",
}


def order_resources(resources):
    return [r for r in RESOURCE_ORDER if r in resources]


@dataclass
class ResourceInput:
    name: str
    production_per_work: float
    price_now: Optional[float] = None
    price_worst: Optional[float] = None
    price_best: Optional[float] = None
    # Yalnız bonuslu resurs üçün: bonus olmasaydı istehsalın nə qədər olacağı.
    alt_production_per_work: Optional[float] = None


@dataclass
class GameInput:
    health: float
    diamonds: float
    use_existing_balance: bool = True
    package_diamonds: float = 0.0
    package_price_m: float = 0.0
    bonus_active: bool = False
    bonus_resource_name: Optional[str] = None
    bonus_per_work_m: float = 0.0  # bonuslu fabrikdə 1 çalışma başına əlavə ₼ (istehsaldan asılı olmayaraq)
    resources: list = field(default_factory=list)  # list[ResourceInput]


def total_possible_works(health: float, diamonds: float) -> int:
    total_energy = health + diamonds * HEALTH_TO_DIAMOND_RATE
    return int(total_energy // NET_ENERGY_COST)


def diamond_cost_per_work() -> float:
    return NET_ENERGY_COST / HEALTH_TO_DIAMOND_RATE  # = 19


def work_cost_in_m(package_diamonds: float, package_price_m: float) -> float:
    if package_diamonds <= 0:
        return 0.0
    diamond_price_m = package_price_m / package_diamonds
    return diamond_cost_per_work() * diamond_price_m


def market_batches_needed(production: float, batch_size: float = MARKET_BATCH_SIZE) -> int:
    if production <= 0 or batch_size <= 0:
        return 0
    return math.ceil(production / batch_size)


def format_duration(total_seconds: float) -> str:
    total_seconds = max(0, int(round(total_seconds)))
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days} gün")
    if hours:
        parts.append(f"{hours} saat")
    if minutes:
        parts.append(f"{minutes} dəqiqə")
    if not parts:
        parts.append(f"{seconds} saniyə")
    return ", ".join(parts)


def roi_percent(net_income_m: float, cost_m: float) -> Optional[float]:
    if cost_m <= 0:
        return None
    return (net_income_m / cost_m) * 100


def return_multiple(gross_income_m: float, cost_m: float) -> Optional[float]:
    """Ümumi geri dönüş: bütün gəlirin maya dəyərinə nisbəti."""
    if cost_m <= 0:
        return None
    return gross_income_m / cost_m


def net_multiple(net_income_m: float, cost_m: float) -> Optional[float]:
    """Xalis geri dönüş: xalis qazancın maya dəyərinə nisbəti."""
    if cost_m <= 0:
        return None
    return net_income_m / cost_m


def resource_report(resource: ResourceInput, works: int, cost_per_work_m: float,
                     bonus_active: bool, bonus_resource_name: Optional[str], bonus_per_work_m: float):
    production = round(resource.production_per_work * works, 2)
    is_bonus = bonus_active and resource.name == bonus_resource_name
    total_cost = round(cost_per_work_m * works, 2)
    bonus_income = works * bonus_per_work_m if is_bonus else 0.0

    def calc_for_price(price, prod, include_bonus=False):
        gross_income = prod * price + (bonus_income if include_bonus else 0.0)
        net_income = gross_income - total_cost
        return {
            "gross_income_m": round(gross_income, 2),
            "bonus_income_m": round(bonus_income if include_bonus else 0.0, 2),
            "net_income_m": round(net_income, 2),
            "roi_percent": roi_percent(net_income, total_cost),
            "return_multiple": return_multiple(gross_income, total_cost),
            "net_multiple": net_multiple(net_income, total_cost),
        }

    result = {
        "name": resource.name,
        "production": production,
        "market_batches": market_batches_needed(production),
        "is_bonus": is_bonus,
        "has_price": resource.price_now is not None,
        "total_cost_m": total_cost,
    }

    if resource.price_now is not None:
        result["now"] = calc_for_price(resource.price_now, production, include_bonus=True)
    if resource.price_worst is not None:
        result["worst"] = calc_for_price(resource.price_worst, production, include_bonus=True)
    if resource.price_best is not None:
        result["best"] = calc_for_price(resource.price_best, production, include_bonus=True)

    if is_bonus and resource.alt_production_per_work is not None and resource.price_now is not None:
        # Bonus olmasaydı: nə əlavə istehsal, nə də əlavə ₼ bonusu olmazdı.
        alt_production = round(resource.alt_production_per_work * works, 2)
        alt_now = calc_for_price(resource.price_now, alt_production, include_bonus=False)
        result["alt"] = {
            "production": alt_production,
            "now": alt_now,
            "diff_net_m": round(result["now"]["net_income_m"] - alt_now["net_income_m"], 2),
        }

    return result


def minimal_sale_price(cost_per_work_m: float, production_per_work: float) -> Optional[float]:
    if cost_per_work_m <= 0 or production_per_work <= 0:
        return None
    return cost_per_work_m / production_per_work


def parse_money(text: str) -> float:
    """
    İstifadəçinin qısaldılmış yazdığı miqdarı rəqəmə çevirir.
    "20000" -> 20000.0
    "20k" -> 20000.0 (k = ×1 000)
    "1kkk" -> 1000000.0 ("kkk" ardıcıllığı "M" ilə eynidir)
    "1m/1M" -> 1000000.0
    "1.5k" -> 1500.0
    """
    t = text.strip().lower().replace(" ", "")
    if not t:
        raise ValueError("boş mətn")
    t = t.replace("kkk", "m")
    multiplier = 1.0
    if t.endswith("m"):
        multiplier = 1_000_000.0
        t = t[:-1]
    elif t.endswith("k"):
        multiplier = 1_000.0
        t = t[:-1]
    if not t:
        t = "1"
    return float(t) * multiplier


def try_parse_money(text: str) -> Optional[float]:
    try:
        return parse_money(text)
    except (ValueError, TypeError):
        return None


def parse_package_price(text: str) -> float:
    """Paket qiyməti üçün xüsusi parser: şəkilçi (k/m/M/kkk) yazılmayıbsa,
    dəyər avtomatik milyon kimi qəbul olunur (paket qiymətləri adətən
    milyonlarla olur), çünki "120" yazan istifadəçi "120M" nəzərdə tutur."""
    t = text.strip().lower().replace(" ", "")
    if not t:
        raise ValueError("boş mətn")
    has_suffix = t.endswith("m") or t.endswith("k") or "kkk" in t
    value = parse_money(text)
    if not has_suffix:
        value *= 1_000_000.0
    return value


def try_parse_package_price(text: str) -> Optional[float]:
    try:
        return parse_package_price(text)
    except (ValueError, TypeError):
        return None


def humanize_m(value: float) -> str:
    sign = "-" if value < 0 else ""
    v = abs(value)
    if v >= 1_000_000_000_000:
        return f"{sign}{v/1_000_000_000_000:,.2f}T"
    if v >= 1_000_000_000:
        return f"{sign}{v/1_000_000_000:,.2f}B"
    if v >= 1_000_000:
        return f"{sign}{v/1_000_000:,.2f}M"
    if v >= 1_000:
        return f"{sign}{v/1_000:,.2f}k"
    return f"{sign}{v:,.2f}"


def humanize_number(value: float) -> str:
    return f"{value:,.0f}".replace(",", " ")


def format_price(value: Optional[float]) -> str:
    if value is None:
        return "tətbiq olunmur"
    if value == 0:
        return "0"
    if abs(value) >= 1:
        return f"{value:,.2f}"
    s = f"{value:.6f}".rstrip("0").rstrip(".")
    return s if s else "0"


def full_analysis(game_input: GameInput):
    works = total_possible_works(game_input.health, game_input.diamonds)

    if game_input.use_existing_balance:
        cost_per_work = 0.0
    else:
        cost_per_work = work_cost_in_m(game_input.package_diamonds, game_input.package_price_m)

    reports = []
    for res in game_input.resources:
        rep = resource_report(res, works, cost_per_work,
                               game_input.bonus_active, game_input.bonus_resource_name,
                               game_input.bonus_per_work_m)
        rep["min_sale_price"] = minimal_sale_price(cost_per_work, res.production_per_work)
        reports.append(rep)

    priced_reports = [r for r in reports if r.get("has_price")]

    def best_for(scenario):
        candidates = [r for r in priced_reports if scenario in r]
        if not candidates:
            return None
        return max(candidates, key=lambda r: r[scenario]["net_income_m"])

    best_now = best_for("now")
    best_worst = best_for("worst")
    best_best = best_for("best")

    total_seconds = works * WORK_INTERVAL_SECONDS

    return {
        "total_works": works,
        "total_duration_seconds": total_seconds,
        "cost_per_work_m": round(cost_per_work, 4),
        "reports": reports,
        "best_now": best_now["name"] if best_now else None,
        "best_worst": best_worst["name"] if best_worst else None,
        "best_best": best_best["name"] if best_best else None,
    }
