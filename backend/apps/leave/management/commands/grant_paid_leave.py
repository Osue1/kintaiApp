"""有給の自動付与バッチ（設計書 第6.1章・第11章「毎日02:00 付与・失効」）。

出勤率8割を下回る場合は自動付与せず、管理者へアラートを出す（自動で付与しないことが
重要、と設計書に明記されている）。ローカル/デモでは cron を組む代わりに手動で実行する。
"""
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.attendance.models import TimeRecord
from apps.attendance.services.records import resolve_day_type
from apps.leave.models import LeaveAbsencePeriod, LeaveRequest, LeaveRequestStatus, PaidLeaveGrant
from apps.leave.services.balance import GrantLot, plan_carryover_expiry
from apps.leave.services.grant import (
    GrantRuleRow,
    calc_attendance_rate,
    meets_attendance_requirement,
    months_between,
    resolve_grant_days,
)
from apps.notifications.services import notify


def _add_months(d, months: int):
    import calendar
    from datetime import date

    total = d.month - 1 + months
    year = d.year + total // 12
    month = total % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


class Command(BaseCommand):
    help = "勤続月数に応じた有給休暇の自動付与を行う（出勤率8割未満は付与せずアラート）"

    def handle(self, *args, **options) -> None:
        today = timezone.localdate()
        users = User.objects.filter(
            role=Role.EMPLOYEE, is_active=True, hire_date__isnull=False
        ).select_related("leave_policy")

        for user in users:
            policy = user.leave_policy or _default_policy()
            if policy is None:
                self.stdout.write(f"スキップ（ポリシー未設定）: {user.name}")
                continue

            months = months_between(user.hire_date, today)
            rules = tuple(
                GrantRuleRow(r.months_of_service, r.granted_days, r.prorated_weekly_days)
                for r in policy.grant_rules.filter(prorated_weekly_days__isnull=True)
            )
            applicable_milestones = sorted({r.months_of_service for r in rules if r.months_of_service <= months})
            if not applicable_milestones:
                continue
            milestone = applicable_milestones[-1]
            note = f"勤続{milestone}ヶ月付与"
            if PaidLeaveGrant.objects.filter(user=user, source_note=note).exists():
                continue

            days = resolve_grant_days(rules, milestone)
            if not days:
                continue

            granted_on = _add_months(user.hire_date, milestone)
            if granted_on > today:
                continue

            rate = _attendance_rate(user, granted_on)
            if not meets_attendance_requirement(rate, policy.required_attendance_rate):
                self.stdout.write(f"付与見送り（出勤率 {rate:.1%}）: {user.name}")
                notify(
                    user,
                    "reminder",
                    "有給休暇が自動付与されませんでした",
                    f"出勤率が基準（{policy.required_attendance_rate:.0%}）を下回ったため、管理者にご確認ください。",
                )
                continue

            with transaction.atomic():
                PaidLeaveGrant.objects.create(
                    user=user,
                    policy=policy,
                    granted_on=granted_on,
                    days=days,
                    expires_on=_add_years(granted_on, policy.expiry_years),
                    source_note=note,
                )
                expired_total = _apply_carryover_limit(user, policy, granted_on)
            self.stdout.write(self.style.SUCCESS(f"付与: {user.name} +{days}日（{granted_on}）"))
            notify(user, "info", "有給休暇が付与されました", f"{granted_on} に{days}日付与されました。")
            if expired_total > 0:
                self.stdout.write(f"繰越上限超過により失効: {user.name} -{expired_total}日")
                notify(
                    user,
                    "reminder",
                    "繰越上限超過により有給休暇が失効しました",
                    f"繰越上限（{policy.carryover_limit_days}日）を超えた {expired_total}日分が失効しました。",
                )


def _apply_carryover_limit(user, policy, granted_on) -> Decimal:
    """新しい付与の直前時点での繰越分に上限を適用し、超過分を強制失効させる
    （設計書 第6.2章）。失効させた合計日数を返す。

    強制失効は、対象ロットの days を直接減らして source_note に記録する方式で表現する
    （このスキーマには「部分失効」を表す専用テーブルが無いため）。
    """
    if policy.carryover_limit_days is None:
        return Decimal("0")

    prior_grants = list(
        PaidLeaveGrant.objects.filter(user=user, granted_on__lt=granted_on).prefetch_related("consumptions")
    )
    prior_lots = tuple(
        GrantLot(
            id=g.id,
            days=g.days,
            expires_on=g.expires_on,
            consumed=sum((c.days for c in g.consumptions.all()), Decimal("0")),
        )
        for g in prior_grants
    )
    actions = plan_carryover_expiry(prior_lots, as_of=granted_on, carryover_limit_days=policy.carryover_limit_days)
    if not actions:
        return Decimal("0")

    grants_by_id = {g.id: g for g in prior_grants}
    total = Decimal("0")
    for action in actions:
        grant = grants_by_id[action.grant_id]
        grant.days -= action.days
        grant.source_note = f"{grant.source_note}／繰越上限超過により{action.days}日失効（{granted_on}）"
        grant.save(update_fields=["days", "source_note"])
        total += action.days
    return total


def _default_policy():
    from apps.leave.models import PaidLeavePolicy

    return PaidLeavePolicy.objects.filter(is_default=True).first()


def _add_years(d, years: int):
    from datetime import date

    try:
        return date(d.year + years, d.month, d.day)
    except ValueError:
        # 2/29 生まれの調整
        return date(d.year + years, d.month, d.day - 1)


def _attendance_rate(user, granted_on) -> float:
    """直近1年（または入社日から）の出勤率。打刻実績がまだ無い期間は満たす扱いにする。"""
    from decimal import Decimal

    period_start = max(user.hire_date, granted_on - timedelta(days=365))
    period_end = granted_on - timedelta(days=1)
    if period_end < period_start:
        return Decimal("1")

    scheduled_days = 0
    attended_days = 0
    absences = list(LeaveAbsencePeriod.objects.filter(user=user))
    leave_dates = set()
    for lr in LeaveRequest.objects.filter(
        user=user, status=LeaveRequestStatus.APPROVED, start_date__lte=period_end, end_date__gte=period_start
    ):
        d = max(lr.start_date, period_start)
        while d <= min(lr.end_date, period_end):
            leave_dates.add(d)
            d += timedelta(days=1)

    worked_dates = set(
        TimeRecord.objects.filter(
            user=user, work_date__gte=period_start, work_date__lte=period_end, clock_in_at__isnull=False
        ).values_list("work_date", flat=True)
    )

    d = period_start
    while d <= period_end:
        if resolve_day_type(user.work_pattern, d) == "business":
            scheduled_days += 1
            if d in worked_dates or d in leave_dates or any(a.covers(d) for a in absences):
                attended_days += 1
        d += timedelta(days=1)

    return calc_attendance_rate(scheduled_days, attended_days)
