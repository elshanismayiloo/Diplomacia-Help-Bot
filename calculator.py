# -*- coding: utf-8 -*-
"""
Diplomacia Profit Calculator - hesablama məntiqi.

Oyun mexanikası:
- 1 çalışma = 100 enerji, bunun 5-i sağlamlıq indeksi hesabına pulsuz
  regenerasiya olunur -> faktiki xərc 95 enerji (💊).
- 💊 -> 💎 nisbəti: 5 💊 = 1 💎 (yəni 95 💊 = 19 💎).
- Almaz paketi: X 💎 = Y M (bazar qiyməti). Bu, 1 çalışmanın M-lə maya
  dəyərini hesablamaq üçün istifadə olunur - AMMA yalnız istifadəçi yeni
  paket alaraq hesablamaq istəyəndə. Mövcud (onsuz da sahib olduğu) balans
  üzərindən hesablananda maya dəyəri sıfır qəbul olunur.
- Bazarda 1 dəfəyə maksimum 20 000 ədəd/barrel satıla bilər.
"""

import math
from dataclasses import dataclass, field
from typing import Optional

ENERGY_PER_WORK = 100
FREE_REGEN_PER_WORK = 5
NET_ENERGY_COST = ENERGY_PER_WORK - FREE_REGEN_PER_WORK  # 95
HEALTH_TO_DIAMOND_RATE = 5  # 5 💊 = 1 💎
MARKET_BATCH_SIZE = 20000   # bazarda 1 dəfəyə satıla bilən maksimum miqdar

RESOURCE_UNITS = {
    "🦌": "ədəd",
    "🪙": "ədəd",
    "🛢": "barrel",
    "⚗️": "ədəd",
}


@dataclass
class ResourceInput:
    name: str                  # məs: "🦌"
    production_per_work: float
    price_now: Optional[float] = None
    price_worst: Optional[float] = None
    price_best: Optional[float] = None
    is_bonus_factory: bool = False


@dataclass
class GameInput:
    health: float               # 💊 balansı
    diamonds: float              # 💎 balansı
    use_existing_balance: bool = True   # True: mövcud balans (maya dəyəri 0), False: yeni paket alınır
    package_diamonds: float = 0.0       # paketdəki 💎 miqdarı (yalnız use_existing_balance=False olanda)
    package_price_m: float = 0.0        # paketin M qiyməti
    bonus_active: bool = False
    bonus_resource_name: Optional[str] = None
    bonus_per_work_m: float = 0.0       # bonuslu fabrikdə 1 çalışma başına əlavə qazanc (M)
    resources: list = field(default_factory=list)  # list[ResourceInput]


def total_possible_works(health: float, diamonds: float) -> int:
    """💊 və 💎 birlikdə neçə çalışma edə bilər."""
    total_energy = health + diamonds * HEALTH_TO_DIAMOND_RATE
    return int(total_energy // NET_ENERGY_COST)


def diamond_cost_per_work() -> float:
    """1 çalışmanın 💎 dəyəri (əgər tam diamondla enerji doldurulsa)."""
    return NET_ENERGY_COST / HEALTH_TO_DIAMOND_RATE  # = 19


def work_cost_in_m(package_diamonds: float, package_price_m: float) -> float:
    """1 çalışmanın M-lə maya dəyəri, paket qiymətinə əsasən."""
    if package_diamonds <= 0:
        return 0.0
    diamond_price_m = package_price_m / package_diamonds
    return diamond_cost_per_work() * diamond_price_m


def market_batches_needed(production: float, batch_size: float = MARKET_BATCH_SIZE) -> int:
    """Bu miqdarı bazarda satmaq üçün minimum neçə dəfə satışa qoymaq lazımdır."""
    if production <= 0 or batch_size <= 0:
        return 0
    return math.ceil(production / batch_size)


def resource_report(resource: ResourceInput, works: int, cost_per_work_m: float,
                     bonus_active: bool, bonus_resource_name: Optional[str], bonus_per_work_m: float):
    """Bir resurs üzrə tam hesabat (indiki / durğun / hərəkətli bazar ssenariləri)."""
    production = round(resource.production_per_work * works, 2)
    is_bonus = bonus_active and resource.name == bonus_resource_name

    def calc_for_price(price):
        gross_revenue = production * price
        bonus_income = works * bonus_per_work_m if is_bonus else 0.0
        gross_income = gross_revenue + bonus_income
        total_cost = cost_per_work_m * works
        net_income = gross_income - total_cost
        return {
            "gross_income_m": round(gross_income, 2),
            "bonus_income_m": round(bonus_income, 2),
            "total_cost_m": round(total_cost, 2),
            "net_income_m": round(net_income, 2),
        }

    result = {
        "name": resource.name,
        "production": production,
        "market_batches": market_batches_needed(production),
        "is_bonus": is_bonus,
        "has_price": resource.price_now is not None,
    }
    if resource.price_now is not None:
        result["now"] = calc_for_price(resource.price_now)
        if resource.price_worst is not None:
            result["worst"] = calc_for_price(resource.price_worst)
        if resource.price_best is not None:
            result["best"] = calc_for_price(resource.price_best)
    return result


def break_even_price(cost_per_work_m: float, production_per_work: float) -> Optional[float]:
    """Bu qiymətdən aşağı düşsə itki başlayır. Mövcud balans rejimində (maya dəyəri 0)
    tətbiq olunmur -> None qaytarır."""
    if cost_per_work_m <= 0:
        return None
    if production_per_work <= 0:
        return None
    return cost_per_work_m / production_per_work


def parse_money(text: str) -> float:
    """
    İstifadəçinin qısaldılmış yazdığı miqdarı rəqəmə çevirir.
    Dəstəklənən formatlar:
      "20000"           -> 20000.0
      "20k" / "20K"     -> 20000.0        (k = ×1 000)
      "1kkk"            -> 1000000.0      ("kkk" ardıcıllığı "M" ilə eynidir)
      "1m" / "1M"       -> 1000000.0      (m/M = ×1 000 000)
      "1.5k"            -> 1500.0
    ValueError qaldırır, əgər mətn rəqəmə çevrilə bilmirsə.
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
    """parse_money-nin xətasız versiyası - uğursuz olarsa None qaytarır."""
    try:
        return parse_money(text)
    except (ValueError, TypeError):
        return None


def humanize_m(value: float) -> str:
    """Böyük dəyərləri qısaldır: 201134688 -> '201.13M', 5200 -> '5.20k'."""
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
    """Sadə min ayırıcılı format (istehsal miqdarları üçün): 6285459 -> '6 285 459'"""
    return f"{value:,.0f}".replace(",", " ")


def humanize_multiplier(net_income_m: float, cost_m: float) -> str:
    """Qoyuluşun neçə dəfə qazandırdığını göstərir. Maya dəyəri 0-dırsa (mövcud
    balans rejimi) bunu tətbiq etmək mənasız olduğu üçün boş sətir qaytarır."""
    if cost_m <= 0:
        return ""
    times = net_income_m / cost_m
    sign = "-" if times < 0 else ""
    t = abs(times)
    if t >= 1_000_000:
        return f"{sign}{t/1_000_000:,.2f}M dəfə"
    if t >= 1_000:
        return f"{sign}{t/1_000:,.2f}k dəfə"
    return f"{sign}{t:,.2f} dəfə"


def format_price(value: Optional[float]) -> str:
    """Zərər həddi kimi kiçik qiymətləri k/M olmadan, adekvat dəqiqliklə göstərir."""
    if value is None:
        return "tətbiq olunmur"
    if value == 0:
        return "0"
    if abs(value) >= 1:
        return f"{value:,.2f}"
    # çox kiçik dəyərlər üçün mənalı rəqəmləri saxla
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
        rep["break_even_price"] = break_even_price(cost_per_work, res.production_per_work)
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

    return {
        "total_works": works,
        "cost_per_work_m": round(cost_per_work, 4),
        "reports": reports,
        "best_now": best_now["name"] if best_now else None,
        "best_worst": best_worst["name"] if best_worst else None,
        "best_best": best_best["name"] if best_best else None,
    }
