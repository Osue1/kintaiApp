"""打刻・日次集計・月次締めのオーケストレーション層。

労働時間の計算式そのものは apps.attendance.services.worktime の純関数に任せ、
ここでは ORM とのやり取り（値オブジェクトへの変換・保存・ロックの強制）だけを扱う。
"""
from __future__ import annotations

from datetime import date, datetime

from django.db import transaction
from django.utils import timezone

from apps.attendance.models import BreakMode as ModelBreakMode
from apps.attendance.models import (
    BreakRecord,
    DailySummary,
    DayType,
    MonthlyAttendance,
    MonthlyStatus,
    RecordSource,
    TimeRecord,
    WorkPattern,
)
from apps.attendance.services import worktime as wt


class MonthLockedError(Exception):
    """承認済みでロックされた期間は打刻・修正できない（設計書 第4.1章①）。"""


def resolve_day_type(work_pattern: WorkPattern | None, target_date: date) -> str:
    from apps.attendance.models import HolidayCalendar

    calendar_row = HolidayCalendar.objects.filter(date=target_date).first()
    if calendar_row is not None:
        return calendar_row.day_type

    if work_pattern is None:
        return DayType.BUSINESS
    weekday = target_date.weekday()
    iso_dow = (weekday + 1) % 7  # Python: 月=0..日=6 → 設計書の 0=日曜…6=土曜 に合わせる
    if work_pattern.statutory_holiday_dow is not None and iso_dow == work_pattern.statutory_holiday_dow:
        return DayType.STATUTORY_HOLIDAY
    if iso_dow in (work_pattern.holiday_dow or []):
        return DayType.COMPANY_HOLIDAY
    return DayType.BUSINESS


def _pattern_spec(work_pattern: WorkPattern | None) -> wt.WorkPatternSpec:
    if work_pattern is None:
        return wt.WorkPatternSpec()
    mode = wt.BreakMode.PUNCH if work_pattern.break_mode == ModelBreakMode.PUNCH else wt.BreakMode.AUTO_DEDUCT
    rules = tuple(wt.BreakRule(r["over"], r["deduct"]) for r in work_pattern.break_rules or [])
    return wt.WorkPatternSpec(
        scheduled_minutes=work_pattern.scheduled_minutes, break_mode=mode, break_rules=rules
    )


def _ensure_unlocked(user, target_date: date) -> None:
    year_month = target_date.strftime("%Y-%m")
    locked = MonthlyAttendance.objects.filter(
        user=user, year_month=year_month, locked_at__isnull=False
    ).exists()
    if locked:
        raise MonthLockedError(f"{year_month} は月次承認済みのため変更できません。")


@transaction.atomic
def clock_in(user, at: datetime | None = None) -> TimeRecord:
    at = at or timezone.now()
    work_date = timezone.localtime(at).date()
    _ensure_unlocked(user, work_date)
    record, _ = TimeRecord.objects.get_or_create(
        user=user,
        work_date=work_date,
        defaults={
            "clock_in_at": at,
            "day_type": resolve_day_type(user.work_pattern, work_date),
            "source": RecordSource.PUNCH,
        },
    )
    if record.clock_in_at is None:
        record.clock_in_at = at
        record.save(update_fields=["clock_in_at", "updated_at"])
    return record


@transaction.atomic
def clock_out(user, at: datetime | None = None) -> TimeRecord:
    at = at or timezone.now()
    work_date = timezone.localtime(at).date()
    _ensure_unlocked(user, work_date)
    record = TimeRecord.objects.filter(user=user, work_date=work_date).first()
    if record is None or record.clock_in_at is None:
        raise ValueError("出勤打刻がありません。")
    record.clock_out_at = at
    record.save(update_fields=["clock_out_at", "updated_at"])
    recompute_summary(record)
    return record


@transaction.atomic
def start_break(user, at: datetime | None = None) -> BreakRecord:
    at = at or timezone.now()
    work_date = timezone.localtime(at).date()
    record = TimeRecord.objects.get(user=user, work_date=work_date)
    return BreakRecord.objects.create(time_record=record, start_at=at)


@transaction.atomic
def end_break(user, at: datetime | None = None) -> BreakRecord:
    at = at or timezone.now()
    work_date = timezone.localtime(at).date()
    record = TimeRecord.objects.get(user=user, work_date=work_date)
    break_record = record.breaks.filter(end_at__isnull=True).order_by("-start_at").first()
    if break_record is None:
        raise ValueError("開始中の休憩がありません。")
    break_record.end_at = at
    break_record.save(update_fields=["end_at"])
    return break_record


def recompute_summary(record: TimeRecord) -> DailySummary | None:
    if record.clock_in_at is None or record.clock_out_at is None:
        return None
    breaks = tuple((b.start_at, b.end_at) for b in record.breaks.filter(end_at__isnull=False))
    punch = wt.PunchInput(
        clock_in_at=record.clock_in_at,
        clock_out_at=record.clock_out_at,
        breaks=breaks,
        day_type=wt.DayType(record.day_type),
    )
    calc = wt.calculate_daily(punch, _pattern_spec(record.user.work_pattern))
    summary, _ = DailySummary.objects.update_or_create(
        time_record=record,
        defaults={
            "worked_minutes": calc.worked_minutes,
            "break_minutes": calc.break_minutes,
            "overtime_within_legal": calc.overtime_within_legal,
            "overtime_statutory": calc.overtime_statutory,
            "night_minutes": calc.night_minutes,
            "holiday_minutes": calc.holiday_minutes,
            "warnings": list(calc.warnings),
        },
    )
    return summary


@transaction.atomic
def apply_correction(correction_request) -> TimeRecord:
    """承認済みの打刻修正依頼を time_record へ適用する。"""
    user = correction_request.user
    work_date = correction_request.work_date
    _ensure_unlocked(user, work_date)
    record, _ = TimeRecord.objects.get_or_create(
        user=user,
        work_date=work_date,
        defaults={"day_type": resolve_day_type(user.work_pattern, work_date)},
    )
    if correction_request.requested_clock_in_at is not None:
        record.clock_in_at = correction_request.requested_clock_in_at
    if correction_request.requested_clock_out_at is not None:
        record.clock_out_at = correction_request.requested_clock_out_at
    record.source = RecordSource.ADMIN_CORRECTION
    record.save(update_fields=["clock_in_at", "clock_out_at", "source", "updated_at"])
    recompute_summary(record)
    return record


_EMPTY_MONTHLY_TOTALS = {
    "work_days": 0,
    "worked_minutes": 0,
    "overtime_within_legal_minutes": 0,
    "overtime_statutory_minutes": 0,
    "night_minutes": 0,
    "holiday_minutes": 0,
}


def _accumulate_daily_summary(totals: dict, summary) -> None:
    """DailySummary 1日分を月次集計の totals 辞書へ加算する
    （aggregate_monthly / aggregate_monthly_bulk で計算ロジックを共用するために切り出した）。"""
    if summary.worked_minutes > 0:
        totals["work_days"] += 1
    totals["worked_minutes"] += summary.worked_minutes
    totals["overtime_within_legal_minutes"] += summary.overtime_within_legal
    totals["overtime_statutory_minutes"] += summary.overtime_statutory
    totals["night_minutes"] += summary.night_minutes
    totals["holiday_minutes"] += summary.holiday_minutes


def aggregate_monthly(user, year_month: str) -> MonthlyAttendance:
    """DailySummary を集計して月次サマリーを更新する（提出・承認前の下書き状態でも呼べる）。

    1人分の呼び出しに特化しており、多数のユーザーをまとめて評価する場面
    （管理者アラート画面など）でユーザー数だけループ呼び出しすると、人数に比例して
    クエリが増えるN+1問題を引き起こす。そのような場面では aggregate_monthly_bulk を使うこと。
    """
    year, month = (int(p) for p in year_month.split("-"))
    records = TimeRecord.objects.filter(
        user=user, work_date__year=year, work_date__month=month
    ).select_related("summary")

    totals = dict(_EMPTY_MONTHLY_TOTALS)
    for record in records:
        summary = getattr(record, "summary", None)
        if summary is not None:
            _accumulate_daily_summary(totals, summary)

    monthly, _ = MonthlyAttendance.objects.update_or_create(
        user=user, year_month=year_month, defaults=totals
    )
    return monthly


def aggregate_monthly_bulk(employees, year_month: str) -> dict[int, MonthlyAttendance]:
    """aggregate_monthly の複数ユーザー一括版（N+1回避）。

    人数分ループで aggregate_monthly を呼ぶと、1人あたり「TimeRecord取得1回＋
    MonthlyAttendanceのupdate_or_create（SELECT+UPDATE/INSERT）」でユーザー数×3クエリ前後が
    発生してしまう。ここでは対象ユーザー全員分のTimeRecordを1クエリで取得してPython側で
    ユーザーごとに集計し、MonthlyAttendanceへの反映は bulk_create(update_conflicts=True) で
    1回のupsertにまとめる（MonthlyAttendance.Meta の UniqueConstraint(user, year_month) を
    衝突キーとして利用）。最後に確定値を読み直すため合計2〜3クエリで完結し、
    ユーザー数が増えてもクエリ数は増えない。集計結果は aggregate_monthly を1人ずつ
    呼んだ場合と同一になる。
    """
    year, month = (int(p) for p in year_month.split("-"))
    records = (
        TimeRecord.objects.filter(user__in=employees, work_date__year=year, work_date__month=month)
        .select_related("summary")
    )

    totals_by_user_id: dict[int, dict] = {}
    for record in records:
        summary = getattr(record, "summary", None)
        if summary is None:
            continue
        totals = totals_by_user_id.setdefault(record.user_id, dict(_EMPTY_MONTHLY_TOTALS))
        _accumulate_daily_summary(totals, summary)

    objs = [
        MonthlyAttendance(
            user_id=employee.id,
            year_month=year_month,
            **totals_by_user_id.get(employee.id, _EMPTY_MONTHLY_TOTALS),
        )
        for employee in employees
    ]
    if objs:
        MonthlyAttendance.objects.bulk_create(
            objs,
            update_conflicts=True,
            unique_fields=["user", "year_month"],
            update_fields=list(_EMPTY_MONTHLY_TOTALS.keys()),
        )

    # update_conflicts=True 時、bulk_create の戻り値には更新分のPKが正しく載らない場合があるため
    # （Djangoの既知の制約）、確定値は改めてまとめて1クエリで読み直す。
    return {
        monthly.user_id: monthly
        for monthly in MonthlyAttendance.objects.filter(user__in=employees, year_month=year_month)
    }


@transaction.atomic
def submit_monthly(user, year_month: str) -> MonthlyAttendance:
    monthly = aggregate_monthly(user, year_month)
    monthly.status = MonthlyStatus.SUBMITTED
    monthly.submitted_at = timezone.now()
    monthly.save(update_fields=["status", "submitted_at", "updated_at"])
    return monthly


@transaction.atomic
def approve_monthly(monthly: MonthlyAttendance, approver) -> MonthlyAttendance:
    monthly.status = MonthlyStatus.APPROVED
    monthly.approved_by = approver
    monthly.approved_at = timezone.now()
    monthly.locked_at = timezone.now()
    monthly.save(update_fields=["status", "approved_by", "approved_at", "locked_at", "updated_at"])
    return monthly


@transaction.atomic
def reject_monthly(monthly: MonthlyAttendance) -> MonthlyAttendance:
    monthly.status = MonthlyStatus.DRAFT
    monthly.submitted_at = None
    monthly.save(update_fields=["status", "submitted_at", "updated_at"])
    return monthly


@transaction.atomic
def reopen_monthly(monthly: MonthlyAttendance) -> MonthlyAttendance:
    """管理者による明示的な再オープン。監査ログはビュー側で記録する（設計書 第4.1章①）。"""
    monthly.status = MonthlyStatus.SUBMITTED
    monthly.locked_at = None
    monthly.save(update_fields=["status", "locked_at", "updated_at"])
    return monthly
