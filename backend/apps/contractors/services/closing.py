"""締め期間・支払期日の算出（設計書 第8.1章）。

締め日 = 31 のときは月末として自動判定する。支払期日は「締め日の属する月 + 支払月オフセット」の
支払日。土日にあたる場合は前営業日へ繰り上げる（祝日調整は holiday_calendar を持つ
呼び出し側の責務とし、ここでは土日のみを扱う）。
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta


def _resolve_day(year: int, month: int, day: int) -> date:
    """day が月末を超える場合（31指定など）は自動的にその月の末日にする。"""
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last_day))


def _add_months(d: date, months: int) -> tuple[int, int]:
    total = d.month - 1 + months
    return d.year + total // 12, total % 12 + 1


def _adjust_for_weekend(d: date) -> date:
    while d.weekday() >= 5:  # 5=土, 6=日
        d -= timedelta(days=1)
    return d


@dataclass(frozen=True, slots=True)
class ClosingPeriod:
    period_start: date
    period_end: date
    payment_due_date: date


def resolve_closing_period(
    *,
    closing_day: int,
    payment_month_offset: int,
    payment_day: int,
    for_year: int,
    for_month: int,
    previous_period_end: date | None = None,
) -> ClosingPeriod:
    """締め期間＝前回締め日の翌日〜当月の締め日。支払期日＝締め月+オフセットの支払日。"""
    period_end = _resolve_day(for_year, for_month, closing_day)

    if previous_period_end is not None:
        period_start = previous_period_end + timedelta(days=1)
    else:
        prev_year, prev_month = _add_months(date(for_year, for_month, 1), -1)
        period_start = _resolve_day(prev_year, prev_month, closing_day) + timedelta(days=1)

    pay_year, pay_month = _add_months(period_end, payment_month_offset)
    due = _adjust_for_weekend(_resolve_day(pay_year, pay_month, payment_day))
    return ClosingPeriod(period_start=period_start, period_end=period_end, payment_due_date=due)
