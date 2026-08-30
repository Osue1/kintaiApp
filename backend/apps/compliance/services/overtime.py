"""36協定の判定ロジック（設計書 第7章）。

集計対象は「時間外労働＋法定休日労働」（worktime.DailyCalculation.agreement36_minutes）で、
法定内残業は含めない。月間・年間の基本判定と、特別条項を有効にした場合の追加判定
（年720時間・単月100時間未満・複数月平均80時間・月45時間超の回数）を分けて持つ。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Severity(StrEnum):
    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"
    VIOLATION = "violation"


@dataclass(frozen=True, slots=True)
class OvertimePolicy:
    monthly_limit_minutes: int = 2700
    annual_limit_minutes: int = 21600
    warning_threshold_percent: int = 80
    special_clause_enabled: bool = False
    special_annual_limit_minutes: int = 43200
    special_monthly_limit_minutes: int = 6000
    special_monthly_over_limit_max_times: int = 6


def _threshold(limit: int, percent: int) -> float:
    return limit * percent / 100


def judge_monthly(minutes: int, policy: OvertimePolicy) -> Severity:
    """月間の時間外＋休日労働。既定45時間（設計書 第7章）。"""
    if minutes >= policy.monthly_limit_minutes:
        return Severity.CRITICAL
    if minutes >= _threshold(policy.monthly_limit_minutes, policy.warning_threshold_percent):
        return Severity.WARNING
    return Severity.OK


def judge_annual(minutes: int, policy: OvertimePolicy) -> Severity:
    """年間の時間外。既定360時間。特別条項の有無にかかわらず、通常枠の目安として評価する。"""
    if minutes >= policy.annual_limit_minutes:
        return Severity.CRITICAL
    if minutes >= _threshold(policy.annual_limit_minutes, policy.warning_threshold_percent):
        return Severity.WARNING
    return Severity.OK


def judge_special_annual(minutes: int, policy: OvertimePolicy) -> Severity:
    """特別条項時の年間上限（既定720時間）。超えたら違反（設計書 第7章）。"""
    if not policy.special_clause_enabled:
        return Severity.OK
    return Severity.VIOLATION if minutes >= policy.special_annual_limit_minutes else Severity.OK


def judge_special_monthly(minutes: int, policy: OvertimePolicy) -> Severity:
    """特別条項時の単月上限（既定100時間未満）。特別条項が無効なら評価しない。"""
    if not policy.special_clause_enabled:
        return Severity.OK
    return Severity.VIOLATION if minutes >= policy.special_monthly_limit_minutes else Severity.OK


def judge_monthly_over_count(over_45_count_this_year: int, policy: OvertimePolicy) -> Severity:
    """月45時間超の回数。5回目でWARNING、既定回数（6回）を超えたらVIOLATION（設計書 第7章）。"""
    if not policy.special_clause_enabled:
        return Severity.OK
    if over_45_count_this_year > policy.special_monthly_over_limit_max_times:
        return Severity.VIOLATION
    if over_45_count_this_year >= 5:
        return Severity.WARNING
    return Severity.OK


def judge_multi_month_average(average_minutes: float, policy: OvertimePolicy) -> Severity:
    """直近2〜6ヶ月の各平均が80時間以内か（設計書 第7章・第7.1章）。"""
    if not policy.special_clause_enabled:
        return Severity.OK
    threshold_minutes = 80 * 60
    return Severity.VIOLATION if average_minutes >= threshold_minutes else Severity.OK


def landing_forecast_minutes(
    elapsed_minutes: int, elapsed_business_days: int, total_business_days: int
) -> int:
    """着地見込み = 月初からの実績 ÷ 経過営業日数 × 当月の総営業日数（設計書 第7.1章）。

    月初5営業日は母数が小さく振れるため、呼び出し側で elapsed_business_days < 5 のときは
    判定を開始しない（設計書どおり、この関数自体は境界を判定しない）。
    """
    if elapsed_business_days <= 0:
        return 0
    return round(elapsed_minutes / elapsed_business_days * total_business_days)


def judge_forecast(forecast_minutes: int, policy: OvertimePolicy) -> Severity:
    if forecast_minutes > policy.monthly_limit_minutes:
        return Severity.CRITICAL
    if forecast_minutes > _threshold(policy.monthly_limit_minutes, policy.warning_threshold_percent):
        return Severity.WARNING
    return Severity.OK


def rolling_averages(monthly_minutes: list[int], window_sizes: range = range(2, 7)) -> dict[int, float]:
    """直近 monthly_minutes[-w:] の平均を、月数の足りている window サイズ（既定2〜6）ごとに返す。

    monthly_minutes は古い月→新しい月の時系列順。月数が window に満たない場合はその
    window を評価しない（設計書 第7章「直近2〜6ヶ月の各平均」）。
    """
    results: dict[int, float] = {}
    for w in window_sizes:
        if len(monthly_minutes) < w:
            continue
        results[w] = sum(monthly_minutes[-w:]) / w
    return results


def months_over_limit(monthly_minutes: list[int], policy: OvertimePolicy) -> int:
    """月45時間（既定）を超えた月の数。「年6回まで」判定の回数に使う（設計書 第7章）。"""
    return sum(1 for m in monthly_minutes if m >= policy.monthly_limit_minutes)
