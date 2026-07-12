# -*- coding: utf-8 -*-
"""
Diplomacia Profit Calculator - hesablama məntiqi.

Oyun mexanikası:
- 1 çalışma = 100 enerji, bunun 5-i sağlamlıq indeksi hesabına pulsuz
  regenerasiya olunur -> faktiki xərc 95 enerji (💊).
- 💊 -> 💎 nisbəti: 5 💊 = 1 💎 (yəni 95 💊 = 19 💎).
- Almaz paketi: X 💎 = Y M (bazar qiyməti). Bu, 1 çalışmanın M-lə maya
  dəyərini hesablamaq üçün istifadə olunur.
"""

from dataclasses import dataclass, field
from typing import Optional


ENERGY_PER_WORK = 100
FREE_REGEN_PER_WORK = 5
NET_ENERGY_COST = ENERGY_PER_WORK - FREE_REGEN_PER_WORK  # 95
HEALTH_TO_DIAMOND_RATE = 5  # 5 💊 = 1 💎


@dataclass
class ResourceInput:
    name: str                 # məs: "🦌"
    production_per_work: float
    price_now: float
    price_worst: Optional[float] = None
    price_best: Optional[float] = None
    is_bonus_factory: bool = False
    bonus_production_per_work: Optional[float] = None  # bonuslu fabrikdəki istehsal


@dataclass
class GameInput:
    health: float              # 💊 balansı
    diamonds: float            # 💎 balansı
    package_diamonds: float    # paketdəki 💎 miqdarı (məs 50000)
    package_price_m: float     # paketin M qiyməti (məs 120)
    bonus_active: bool = False
    bonus_m_per_50_works: float = 0.0
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


def resource_report(resource: ResourceInput, works: int, cost_per_work_m: float,
                     bonus_active: bool, bonus_m_per_50_works: float):
    """Bir resurs üzrə tam hesabat (indiki / worst / best qiymət ssenariləri)."""

    def calc_for_price(price):
        production = resource.production_per_work * works
        revenue = production * price
        total_cost = cost_per_work_m * works
        bonus_income = 0.0
        if bonus_active and resource.is_bonus_factory:
            bonus_income = (works // 50) * bonus_m_per_50_works
        net_profit = revenue + bonus_income - total_cost
        roi = (net_profit / total_cost * 100) if total_cost > 0 else 0.0
        return {
            "production": round(production, 2),
            "revenue_m": round(revenue, 2),
            "bonus_income_m": round(bonus_income, 2),
            "total_cost_m": round(total_cost, 2),
            "net_profit_m": round(net_profit, 2),
            "roi_percent": round(roi, 2),
        }

    result = {"name": resource.name, "now": calc_for_price(resource.price_now)}
    if resource.price_worst is not None:
        result["worst"] = calc_for_price(resource.price_worst)
    if resource.price_best is not None:
        result["best"] = calc_for_price(resource.price_best)
    return result


def critical_break_even_price(resource: ResourceInput, cost_per_work_m: float) -> float:
    """Bu qiymətdən aşağı düşsə resurs artıq zərər verir (break-even qiymət)."""
    if resource.production_per_work <= 0:
        return float("inf")
    return round(cost_per_work_m / resource.production_per_work, 4)


def humanize_m(value: float) -> str:
    """Böyük M dəyərlərini oxunaqlı formata salır: 201134688 -> '201.13 mln M'"""
    sign = "-" if value < 0 else ""
    v = abs(value)
    if v >= 1_000_000_000_000:
        return f"{sign}{v/1_000_000_000_000:,.2f} trln M"
    if v >= 1_000_000_000:
        return f"{sign}{v/1_000_000_000:,.2f} mlrd M"
    if v >= 1_000_000:
        return f"{sign}{v/1_000_000:,.2f} mln M"
    if v >= 1_000:
        return f"{sign}{v:,.0f} M"
    return f"{sign}{v:,.2f} M"


def humanize_number(value: float) -> str:
    """Sadə min ayırıcılı format (istehsal miqdarları üçün): 6285459 -> '6 285 459'"""
    return f"{value:,.0f}".replace(",", " ")


def humanize_roi(value: float) -> str:
    if abs(value) >= 1_000_000:
        return f"{value/1_000_000:,.1f}M%"
    if abs(value) >= 1_000:
        return f"{value/1_000:,.1f}k%"
    return f"{value:,.1f}%"


def humanize_multiplier(roi_percent: float) -> str:
    """ROI faizini 'neçə dəfə qazandırır' formatına çevirir (nəhəng faizlər üçün daha anlaşıqlıdır)."""
    times = roi_percent / 100.0
    sign = "-" if times < 0 else ""
    t = abs(times)
    if t >= 1_000_000:
        return f"{sign}{t/1_000_000:,.2f} mln dəfə"
    if t >= 1_000:
        return f"{sign}{t/1_000:,.2f} min dəfə"
    return f"{sign}{t:,.2f} dəfə"


def full_analysis(game_input: GameInput):
    works = total_possible_works(game_input.health, game_input.diamonds)
    cost_per_work = work_cost_in_m(game_input.package_diamonds, game_input.package_price_m)

    reports = []
    for res in game_input.resources:
        rep = resource_report(res, works, cost_per_work,
                               game_input.bonus_active, game_input.bonus_m_per_50_works)
        rep["break_even_price"] = critical_break_even_price(res, cost_per_work)
        reports.append(rep)

    best_now = max(reports, key=lambda r: r["now"]["net_profit_m"]) if reports else None
    best_worst = None
    best_best = None
    if reports and "worst" in reports[0]:
        best_worst = max(reports, key=lambda r: r["worst"]["net_profit_m"])
    if reports and "best" in reports[0]:
        best_best = max(reports, key=lambda r: r["best"]["net_profit_m"])

    return {
        "total_works": works,
        "cost_per_work_m": round(cost_per_work, 4),
        "reports": reports,
        "best_now": best_now["name"] if best_now else None,
        "best_worst": best_worst["name"] if best_worst else None,
        "best_best": best_best["name"] if best_best else None,
    }
    diamonds: float            # 💎 balansı
    package_diamonds: float    # paketdəki 💎 miqdarı (məs 50000)
    package_price_m: float     # paketin M qiyməti (məs 120)
    bonus_active: bool = False
    bonus_m_per_50_works: float = 0.0
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


def resource_report(resource: ResourceInput, works: int, cost_per_work_m: float,
                     bonus_active: bool, bonus_m_per_50_works: float):
    """Bir resurs üzrə tam hesabat (indiki / worst / best qiymət ssenariləri)."""

    def calc_for_price(price):
        production = resource.production_per_work * works
        revenue = production * price
        total_cost = cost_per_work_m * works
        bonus_income = 0.0
        if bonus_active and resource.is_bonus_factory:
            bonus_income = (works // 50) * bonus_m_per_50_works
        net_profit = revenue + bonus_income - total_cost
        roi = (net_profit / total_cost * 100) if total_cost > 0 else 0.0
        return {
            "production": round(production, 2),
            "revenue_m": round(revenue, 2),
            "bonus_income_m": round(bonus_income, 2),
            "total_cost_m": round(total_cost, 2),
            "net_profit_m": round(net_profit, 2),
            "roi_percent": round(roi, 2),
        }

    result = {"name": resource.name, "now": calc_for_price(resource.price_now)}
    if resource.price_worst is not None:
        result["worst"] = calc_for_price(resource.price_worst)
    if resource.price_best is not None:
        result["best"] = calc_for_price(resource.price_best)
    return result


def critical_break_even_price(resource: ResourceInput, cost_per_work_m: float) -> float:
    """Bu qiymətdən aşağı düşsə resurs artıq zərər verir (break-even qiymət)."""
    if resource.production_per_work <= 0:
        return float("inf")
    return round(cost_per_work_m / resource.production_per_work, 4)


def full_analysis(game_input: GameInput):
    works = total_possible_works(game_input.health, game_input.diamonds)
    cost_per_work = work_cost_in_m(game_input.package_diamonds, game_input.package_price_m)

    reports = []
    for res in game_input.resources:
        rep = resource_report(res, works, cost_per_work,
                               game_input.bonus_active, game_input.bonus_m_per_50_works)
        rep["break_even_price"] = critical_break_even_price(res, cost_per_work)
        reports.append(rep)

    best_now = max(reports, key=lambda r: r["now"]["net_profit_m"]) if reports else None
    best_worst = None
    best_best = None
    if reports and "worst" in reports[0]:
        best_worst = max(reports, key=lambda r: r["worst"]["net_profit_m"])
    if reports and "best" in reports[0]:
        best_best = max(reports, key=lambda r: r["best"]["net_profit_m"])

    return {
        "total_works": works,
        "cost_per_work_m": round(cost_per_work, 4),
        "reports": reports,
        "best_now": best_now["name"] if best_now else None,
        "best_worst": best_worst["name"] if best_worst else None,
        "best_best": best_best["name"] if best_best else None,
    }
