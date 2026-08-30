"""36協定の総合判定（月次・年次・特別条項・複数月平均・回数）をユーザー単位でまとめる。

判定式そのものは overtime.py の純関数に委譲し、ここでは MonthlyAttendance から
時系列データを取り出すオーケストレーションだけを行う。

「年」は36協定の起算日ではなく暦年（1〜12月）で近似する。起算日を厳密に扱うには
協定の届出日をマスタとして持つ必要があり、現状のスキーマにはない簡略化。
"""
from __future__ import annotations

from dataclasses import dataclass

from apps.attendance.models import MonthlyAttendance

from .overtime import (
    OvertimePolicy,
    Severity,
    judge_annual,
    judge_monthly,
    judge_monthly_over_count,
    judge_multi_month_average,
    judge_special_annual,
    judge_special_monthly,
    months_over_limit,
    rolling_averages,
)

_SEVERITY_RANK = {Severity.OK: 0, Severity.WARNING: 1, Severity.CRITICAL: 2, Severity.VIOLATION: 3}


@dataclass(frozen=True, slots=True)
class OvertimeReason:
    kind: str
    label: str
    severity: Severity


@dataclass(frozen=True, slots=True)
class OvertimeEvaluation:
    current_month_minutes: int
    severity: Severity
    reasons: tuple[OvertimeReason, ...]


def _worst(*severities: Severity) -> Severity:
    return max(severities, key=lambda s: _SEVERITY_RANK[s])


def _agreement36_minutes_values(qs) -> list[int]:
    # overtime_36_minutes は DB カラムではなく Python 側の @property のため、
    # 元になる2カラムを取ってきてここで合算する。
    return [
        row["overtime_statutory_minutes"] + row["holiday_minutes"]
        for row in qs.values("overtime_statutory_minutes", "holiday_minutes")
    ]


def evaluate_user_overtime(user, policy: OvertimePolicy, year_month: str, current_month_minutes: int) -> OvertimeEvaluation:
    """指定ユーザーの当月時点での36協定リスクをまとめて評価する（DBに2回問い合わせる）。

    多数のユーザーをまとめて評価する場面（管理者アラート画面など）でこの関数を人数分
    ループ呼び出しすると、1人あたり2クエリ×人数のN+1問題になる。その場合は
    bulk_fetch_monthly_history() で対象ユーザー全員分を1クエリで先に取得し、
    evaluate_from_history() を使うこと（判定結果はどちらの経路でも同一になる）。
    """
    year = year_month.split("-")[0]

    # 直近6ヶ月（当月含む）の時系列。複数月平均・回数判定に使う。
    prior_qs = (
        MonthlyAttendance.objects.filter(user=user).exclude(year_month=year_month).order_by("-year_month")[:5]
    )
    prior = _agreement36_minutes_values(prior_qs)

    # 暦年（当月含む）の時系列。年間合計・回数判定に使う。
    year_qs = MonthlyAttendance.objects.filter(
        user=user, year_month__gte=f"{year}-01", year_month__lt=f"{year}-13"
    ).exclude(year_month=year_month)
    year_series_excl_current = _agreement36_minutes_values(year_qs)

    return _evaluate_from_series(policy, current_month_minutes, prior, year_series_excl_current)


def bulk_fetch_monthly_history(employees, year_month: str) -> dict[int, list[tuple[str, int]]]:
    """複数ユーザー分の「36協定判定に必要な過去の月次実績」を1クエリでまとめて取得する。

    evaluate_user_overtime が1ユーザーにつき発行する2クエリ（直近5ヶ月分・暦年分）を、
    対象ユーザー全員についてまとめて1回のクエリに集約するための一括取得ヘルパー。
    「直近5ヶ月」が年をまたぐ場合（例: 対象月が1〜4月）に前年分も必要になるため、
    前年1月〜対象年12月の2年分を広めに取得しておき、絞り込みは evaluate_from_history 側で行う。
    戻り値: user_id -> [(year_month, overtime_36_minutes), ...]（対象月自身は含まない）。
    """
    year = int(year_month.split("-")[0])
    rows = (
        MonthlyAttendance.objects.filter(
            user__in=employees, year_month__gte=f"{year - 1}-01", year_month__lt=f"{year}-13"
        )
        .exclude(year_month=year_month)
        .values("user_id", "year_month", "overtime_statutory_minutes", "holiday_minutes")
    )
    history: dict[int, list[tuple[str, int]]] = {}
    for row in rows:
        minutes = row["overtime_statutory_minutes"] + row["holiday_minutes"]
        history.setdefault(row["user_id"], []).append((row["year_month"], minutes))
    return history


def evaluate_from_history(
    policy: OvertimePolicy, year_month: str, current_month_minutes: int, history: list[tuple[str, int]]
) -> OvertimeEvaluation:
    """bulk_fetch_monthly_history() で事前取得した履歴からDBに触れずに評価する。

    history は対象月を含まない (year_month, overtime_36_minutes) のリスト（複数年分含んでいてよい）。
    ここで「直近5ヶ月」「暦年内」の絞り込みを行うため、evaluate_user_overtime とは異なり
    呼び出し1回あたりの追加クエリは発生しない。
    """
    year = year_month.split("-")[0]
    sorted_desc = sorted(history, key=lambda pair: pair[0], reverse=True)
    prior = [minutes for _, minutes in sorted_desc[:5]]
    year_series_excl_current = [minutes for ym, minutes in history if ym.startswith(f"{year}-")]
    return _evaluate_from_series(policy, current_month_minutes, prior, year_series_excl_current)


def _evaluate_from_series(
    policy: OvertimePolicy,
    current_month_minutes: int,
    prior: list[int],
    year_series_excl_current: list[int],
) -> OvertimeEvaluation:
    """判定の本体（DBに依存しない純粋な計算）。evaluate_user_overtime / evaluate_from_history
    の双方から、それぞれの方法で集めた時系列データを渡して呼ばれる共通処理。"""
    recent_series = list(reversed(prior)) + [current_month_minutes]
    year_series = year_series_excl_current + [current_month_minutes]
    annual_minutes = sum(year_series)
    over_count = months_over_limit(year_series, policy)

    reasons: list[OvertimeReason] = []

    monthly_severity = judge_monthly(current_month_minutes, policy)
    if monthly_severity != Severity.OK:
        reasons.append(OvertimeReason("monthly", "当月の時間外が上限に近い、または超過", monthly_severity))

    annual_severity = judge_annual(annual_minutes, policy)
    if annual_severity != Severity.OK:
        reasons.append(OvertimeReason("annual", "年間の時間外が上限に近い、または超過", annual_severity))

    special_annual_severity = judge_special_annual(annual_minutes, policy)
    if special_annual_severity != Severity.OK:
        reasons.append(OvertimeReason("special_annual", "特別条項の年間上限（720時間）を超過", special_annual_severity))

    special_monthly_severity = judge_special_monthly(current_month_minutes, policy)
    if special_monthly_severity != Severity.OK:
        reasons.append(OvertimeReason("special_monthly", "特別条項の単月上限（100時間）を超過", special_monthly_severity))

    over_count_severity = judge_monthly_over_count(over_count, policy)
    if over_count_severity != Severity.OK:
        reasons.append(
            OvertimeReason("monthly_over_count", f"月45時間超が年{over_count}回目", over_count_severity)
        )

    worst_avg_severity = Severity.OK
    worst_avg_window = None
    for window, average in rolling_averages(recent_series).items():
        severity = judge_multi_month_average(average, policy)
        if _SEVERITY_RANK[severity] > _SEVERITY_RANK[worst_avg_severity]:
            worst_avg_severity = severity
            worst_avg_window = window
    if worst_avg_severity != Severity.OK:
        reasons.append(
            OvertimeReason(
                "multi_month_avg", f"直近{worst_avg_window}ヶ月平均が80時間を超過", worst_avg_severity
            )
        )

    overall = _worst(
        monthly_severity,
        annual_severity,
        special_annual_severity,
        special_monthly_severity,
        over_count_severity,
        worst_avg_severity,
    )
    return OvertimeEvaluation(current_month_minutes=current_month_minutes, severity=overall, reasons=tuple(reasons))
