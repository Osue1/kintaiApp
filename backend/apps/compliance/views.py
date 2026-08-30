"""管理者ダッシュボード用の横断エンドポイント。

勤怠承認は attendance / leave の各申請を横断して1つの一覧に見せる必要があり、
アラートは compliance の判定ロジックを複数ドメイン（勤怠・休暇）のデータに適用する。
監査ログの閲覧も、承認・打刻修正・マスタ変更・請求書発行という複数アプリにまたがる
操作履歴を横断して1画面に見せるという点で同じ性質を持つ（以前はDjango管理サイトに
直接入らないと確認できず、アプリ内に閲覧手段が無かった）。
いずれも単一アプリに閉じない読み取り専用の集約なので、ここにまとめる。
"""
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import AuditLog
from apps.accounts.serializers import AuditLogSerializer
from apps.attendance.models import MonthlyAttendance, MonthlyStatus, TimeCorrectionRequest
from apps.attendance.services import records as record_service
from apps.common.permissions import IsAdminRole
from apps.leave.models import LeaveRequest, LeaveRequestStatus, PaidLeaveGrant

from .models import OvertimeLimitPolicy
from .services.evaluation import bulk_fetch_monthly_history, evaluate_from_history
from .services.overtime import OvertimePolicy, Severity

# 監査ログ一覧を無制限に返すと、テーブルが育つほど画面もAPIも重くなる
# （AuditLog/IdempotencyKey/Notificationの保持期限バッチを追加した前イテレーションの
# 課題と同根）。AdminApprovalsViewの各querysetも同様に直近200件で打ち切っており、
# それに倣う。絞り込み条件（action・target_type・期間）と併用すれば実運用上は十分。
AUDIT_LOG_LIST_LIMIT = 200


class AdminApprovalsView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    @extend_schema(summary="承認待ち一覧（勤怠・休暇・修正を横断）")
    def get(self, request: Request) -> Response:
        items = []

        for c in TimeCorrectionRequest.objects.select_related("user").order_by("-created_at")[:200]:
            label = "出勤" if c.requested_clock_in_at else "退勤"
            time_str = (
                timezone.localtime(c.requested_clock_in_at).strftime("%H:%M")
                if c.requested_clock_in_at
                else timezone.localtime(c.requested_clock_out_at).strftime("%H:%M")
            )
            items.append(
                {
                    "id": f"correction-{c.id}",
                    "employee_name": c.user.name,
                    "type": "correction",
                    "summary": f"{c.work_date} {label}打刻の修正依頼（{time_str}）",
                    "detail": c.reason,
                    "requested_at": c.created_at.isoformat(),
                    "status": _map_status(c.status),
                    "rejected_reason": c.rejected_reason,
                }
            )

        for m in MonthlyAttendance.objects.select_related("user").exclude(status=MonthlyStatus.DRAFT).order_by(
            "-submitted_at"
        )[:200]:
            items.append(
                {
                    "id": f"monthly-{m.id}",
                    "employee_name": m.user.name,
                    "type": "monthly",
                    "summary": f"{m.year_month} 分 月次勤怠確定申請",
                    "detail": f"出勤{m.work_days}日・残業{round(m.overtime_36_minutes / 60, 1)}時間",
                    "requested_at": (m.submitted_at or m.updated_at).isoformat(),
                    "status": "approved" if m.status == MonthlyStatus.APPROVED else _map_monthly_status(m.status),
                    "rejected_reason": "",
                }
            )

        for lr in LeaveRequest.objects.select_related("user", "leave_type").order_by("-created_at")[:200]:
            unit_label = {"full": "全日", "half_am": "午前半休", "half_pm": "午後半休"}[lr.unit]
            period = (
                f"{lr.start_date}"
                if lr.start_date == lr.end_date
                else f"{lr.start_date}〜{lr.end_date}"
            )
            items.append(
                {
                    "id": f"leave-{lr.id}",
                    "employee_name": lr.user.name,
                    "type": "leave",
                    "summary": f"{lr.leave_type.name}（{unit_label}）{period}",
                    "detail": lr.reason,
                    "requested_at": lr.created_at.isoformat(),
                    "status": _map_status(lr.status),
                    "rejected_reason": lr.rejected_reason,
                }
            )

        items.sort(key=lambda i: i["requested_at"], reverse=True)
        return Response(items)


def _map_status(status: str) -> str:
    return {"pending": "pending", "approved": "approved", "rejected": "rejected"}.get(status, status)


def _map_monthly_status(status: str) -> str:
    return "pending" if status == MonthlyStatus.SUBMITTED else "approved"


class AdminAlertsView(APIView):
    """有給5日・36協定アラート。

    従業員数が多くなるとN+1クエリでスケールしなくなる典型的な集約画面だったため、
    「1人ずつDBへ問い合わせる」ループを全て「対象者全員分をまとめて数クエリで取得し、
    Python側の辞書引きで各人へ配る」形に書き換えている。個々のクエリ内容は
    元の実装（PaidLeaveGrant最新1件・LeaveRequest消化日数・MonthlyAttendance集計・
    36協定判定用の月次履歴）と同一で、従業員数が増えてもクエリ数がほぼ一定に保たれる点だけが
    異なる（実測はテスト側の django_assert_max_num_queries を参照）。
    """

    permission_classes = [IsAuthenticated, IsAdminRole]

    @extend_schema(summary="有給5日・36協定アラート")
    def get(self, request: Request) -> Response:
        from apps.accounts.models import Role, User

        today = timezone.localdate()
        employees = list(User.objects.filter(role=Role.EMPLOYEE, is_active=True))
        policy_row = OvertimeLimitPolicy.objects.filter(is_default=True).first() or OvertimeLimitPolicy.objects.first()
        policy = (
            OvertimePolicy(
                monthly_limit_minutes=policy_row.monthly_limit_minutes,
                annual_limit_minutes=policy_row.annual_limit_minutes,
                warning_threshold_percent=policy_row.warning_threshold_percent,
                special_clause_enabled=policy_row.special_clause_enabled,
                special_annual_limit_minutes=policy_row.special_annual_limit_minutes,
                special_monthly_limit_minutes=policy_row.special_monthly_limit_minutes,
                special_monthly_over_limit_max_times=policy_row.special_monthly_over_limit_max_times,
            )
            if policy_row
            else OvertimePolicy()
        )

        paid_leave_alerts = _build_paid_leave_alerts(employees, today)
        overtime_alerts = _build_overtime_alerts(employees, policy, today)

        return Response({"paid_leave_alerts": paid_leave_alerts, "overtime_alerts": overtime_alerts})


def _build_paid_leave_alerts(employees: list, today) -> list[dict]:
    """年5日取得義務のアラートを対象者全員分まとめて組み立てる（クエリ数: 最大2）。"""
    # 「ユーザーごとの直近付与」を1クエリで取得する（PostgreSQLのDISTINCT ONを利用）。
    # order_by の先頭がdistinctの対象フィールドと一致している必要がある。
    latest_grants = {
        grant.user_id: grant
        for grant in PaidLeaveGrant.objects.filter(user__in=employees)
        .order_by("user_id", "-granted_on")
        .distinct("user_id")
    }
    candidates = {
        user_id: grant
        for user_id, grant in latest_grants.items()
        if grant.days >= 10 and today <= grant.granted_on + timedelta(days=365)
    }

    # 取得義務の判定対象者分の消化日数を1クエリでまとめて取得し、Python側で
    # 「その人自身の付与日を起点とした365日間」に該当する分だけ合算する
    # （起点日が人によって違うため、DB側の1クエリだけでは絞り込みきれずPythonで絞る）。
    used_by_user: dict[int, Decimal] = {}
    if candidates:
        earliest_start = min(grant.granted_on for grant in candidates.values())
        leave_rows = LeaveRequest.objects.filter(
            user_id__in=candidates.keys(),
            leave_type__counts_toward_mandatory_five=True,
            status=LeaveRequestStatus.APPROVED,
            start_date__gte=earliest_start,
        ).values("user_id", "start_date", "days")
        for row in leave_rows:
            grant = candidates[row["user_id"]]
            window_end = grant.granted_on + timedelta(days=365)
            if grant.granted_on <= row["start_date"] < window_end:
                used_by_user[row["user_id"]] = used_by_user.get(row["user_id"], Decimal("0")) + row["days"]

    employees_by_id = {e.id: e for e in employees}
    alerts = []
    for user_id, grant in candidates.items():
        used_days = used_by_user.get(user_id, Decimal("0"))
        if used_days < 5:
            user = employees_by_id[user_id]
            alerts.append(
                {
                    "employee_id": str(user.id),
                    "employee_name": user.name,
                    "granted_date": grant.granted_on.isoformat(),
                    "used": float(used_days),
                    "required": 5,
                    "deadline": (grant.granted_on + timedelta(days=365)).isoformat(),
                }
            )
    return alerts


def _build_overtime_alerts(employees: list, policy: OvertimePolicy, today) -> list[dict]:
    """36協定アラートを対象者全員分まとめて組み立てる（クエリ数: ほぼ一定）。"""
    year_month = today.strftime("%Y-%m")
    monthly_by_user = record_service.aggregate_monthly_bulk(employees, year_month)
    history_by_user = bulk_fetch_monthly_history(employees, year_month)

    alerts = []
    for user in employees:
        monthly = monthly_by_user.get(user.id)
        current_minutes = monthly.overtime_36_minutes if monthly else 0
        evaluation = evaluate_from_history(
            policy, year_month, current_minutes, history_by_user.get(user.id, [])
        )
        if evaluation.severity != Severity.OK:
            alerts.append(
                {
                    "employee_id": str(user.id),
                    "employee_name": user.name,
                    "month": year_month,
                    "overtime_hours": round(evaluation.current_month_minutes / 60, 1),
                    "limit_hours": round(policy.monthly_limit_minutes / 60, 1),
                    "severity": evaluation.severity.value,
                    "reasons": [{"kind": r.kind, "label": r.label, "severity": r.severity.value} for r in evaluation.reasons],
                }
            )
    return alerts


class AdminAuditLogListView(APIView):
    """監査ログの一覧・絞り込み（設計書 第12.1章）。

    action・target_type・target_id・操作者・期間で絞り込める。件数は
    AUDIT_LOG_LIST_LIMIT で打ち切る（無制限に返すとテーブルが育つほど重くなるため）。
    """

    permission_classes = [IsAuthenticated, IsAdminRole]

    @extend_schema(summary="監査ログの一覧")
    def get(self, request: Request) -> Response:
        qs = AuditLog.objects.select_related("actor").order_by("-created_at")

        action = request.query_params.get("action")
        if action:
            qs = qs.filter(action=action)

        target_type = request.query_params.get("target_type")
        if target_type:
            qs = qs.filter(target_type=target_type)

        target_id = request.query_params.get("target_id")
        if target_id:
            qs = qs.filter(target_id=target_id)

        actor_id = request.query_params.get("actor_id")
        if actor_id:
            qs = qs.filter(actor_id=actor_id)

        date_from = request.query_params.get("date_from")
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)

        date_to = request.query_params.get("date_to")
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        total_count = qs.count()
        rows = qs[:AUDIT_LOG_LIST_LIMIT]
        return Response(
            {
                "results": AuditLogSerializer(rows, many=True).data,
                "total_count": total_count,
                "truncated": total_count > AUDIT_LOG_LIST_LIMIT,
            }
        )
