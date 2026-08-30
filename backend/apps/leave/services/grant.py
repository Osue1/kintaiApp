"""有給の付与判定ロジック（設計書 第6.1章）。

付与日数そのものは paid_leave_grant_rule のテーブル引きで決まる。管理者が自由に
編集できる値なので、ここでは「その勤続月数に該当する行を探す」「出勤率8割を
満たしているか」という、値に依存しない判定だけを純関数として持つ。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class GrantRuleRow:
    months_of_service: int
    granted_days: Decimal
    prorated_weekly_days: int | None = None


def months_between(start: date, end: date) -> int:
    """start から end までの満月数。入社日基準の勤続月数判定に使う。"""
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return max(0, months)


def resolve_grant_days(
    rules: tuple[GrantRuleRow, ...], months_of_service: int, weekly_days: int | None = None
) -> Decimal | None:
    """勤続月数に対応する付与日数を返す。該当なしは None。

    「6ヶ月:10日 / 1年6ヶ月:11日 / …」のようなテーブルは、到達済みの行のうち
    もっとも勤続月数が大きい行が有効になる。
    """
    candidates = [r for r in rules if r.prorated_weekly_days == weekly_days]
    applicable = [r for r in candidates if r.months_of_service <= months_of_service]
    if not applicable:
        return None
    best = max(applicable, key=lambda r: r.months_of_service)
    return best.granted_days


def meets_attendance_requirement(attendance_rate: Decimal, required_rate: Decimal) -> bool:
    """出勤率が要件を満たすか。ちょうど8割は満たす扱い（設計書 13.1 境界値）。"""
    return attendance_rate >= required_rate


def calc_attendance_rate(scheduled_days: int, attended_days: int) -> Decimal:
    """所定労働日数に対する出勤日数の割合。分母0は満たす扱いとして1を返す。"""
    if scheduled_days <= 0:
        return Decimal("1")
    return (Decimal(attended_days) / Decimal(scheduled_days)).quantize(Decimal("0.001"))


def below_statutory_minimum(rules: tuple[GrantRuleRow, ...], statutory: tuple[GrantRuleRow, ...]) -> tuple[int, ...]:
    """法定テーブルを下回る勤続月数の一覧を返す。管理画面の保存時警告に使う（設計書 第6.1章）。"""
    violations: list[int] = []
    for row in statutory:
        actual = resolve_grant_days(rules, row.months_of_service, weekly_days=None)
        if actual is None or actual < row.granted_days:
            violations.append(row.months_of_service)
    return tuple(violations)
