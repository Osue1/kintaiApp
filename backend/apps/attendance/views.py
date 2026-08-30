from datetime import datetime, timedelta

from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.audit import record_audit
from apps.common.idempotency import with_idempotency
from apps.common.permissions import IsAdminRole
from apps.compliance.models import OvertimeLimitPolicy
from apps.notifications.models import Notification
from apps.notifications.services import notify

from .models import (
    CorrectionStatus,
    MonthlyAttendance,
    TimeCorrectionRequest,
    TimeRecord,
)
from .serializers import (
    CorrectionRequestCreateSerializer,
    CorrectionRequestSerializer,
    PunchSerializer,
    RejectSerializer,
)
from .services import records as record_service

WEEKDAY_JA = ["月", "火", "水", "木", "金", "土", "日"]


def _leave_balance_for(user) -> float:
    from decimal import Decimal

    from apps.leave.models import PaidLeaveGrant
    from apps.leave.services.balance import GrantLot
    from apps.leave.services.balance import remaining_days as calc_remaining

    today = timezone.localdate()
    grants = PaidLeaveGrant.objects.filter(user=user).prefetch_related("consumptions")
    lots = tuple(
        GrantLot(
            id=g.id,
            days=g.days,
            expires_on=g.expires_on,
            consumed=sum((c.days for c in g.consumptions.all()), Decimal("0")),
        )
        for g in grants
    )
    return float(calc_remaining(lots, as_of=today))


def _note_for(record: TimeRecord | None, day_type: str, has_pending_correction: bool, has_leave: bool) -> str:
    if has_pending_correction:
        return "pending"
    if has_leave:
        return "leave"
    if record is None or record.clock_in_at is None:
        if day_type != "business":
            return "holiday"
        return "normal"
    return "normal"


def _serialize_record(user, target_date, pending_dates: set, leave_dates: set) -> dict:
    record = TimeRecord.objects.filter(user=user, work_date=target_date).select_related("summary").first()
    day_type = record.day_type if record else record_service.resolve_day_type(user.work_pattern, target_date)
    summary = getattr(record, "summary", None) if record else None
    note = _note_for(record, day_type, target_date in pending_dates, target_date in leave_dates)
    return {
        "date": target_date.isoformat(),
        "weekday": WEEKDAY_JA[target_date.weekday()],
        "clock_in": timezone.localtime(record.clock_in_at).strftime("%H:%M") if record and record.clock_in_at else None,
        "clock_out": timezone.localtime(record.clock_out_at).strftime("%H:%M") if record and record.clock_out_at else None,
        "worked_minutes": summary.worked_minutes if summary else None,
        "note": note,
    }


def _pending_and_leave_dates(user, start, end) -> tuple[set, set]:
    from apps.leave.models import LeaveRequest, LeaveRequestStatus

    pending_dates = set(
        TimeCorrectionRequest.objects.filter(
            user=user, status=CorrectionStatus.PENDING, work_date__gte=start, work_date__lte=end
        ).values_list("work_date", flat=True)
    )
    leave_dates: set = set()
    for lr in LeaveRequest.objects.filter(
        user=user, status=LeaveRequestStatus.APPROVED, start_date__lte=end, end_date__gte=start
    ):
        d = max(lr.start_date, start)
        last = min(lr.end_date, end)
        while d <= last:
            leave_dates.add(d)
            d += timedelta(days=1)
    return pending_dates, leave_dates


class DashboardView(APIView):
    """マイページに必要なデータを1回のリクエストでまとめて返す。"""

    @extend_schema(summary="マイページダッシュボード")
    def get(self, request: Request) -> Response:
        user = request.user
        today = timezone.localdate()

        today_record = TimeRecord.objects.filter(user=user, work_date=today).first()
        if today_record is None or today_record.clock_in_at is None:
            today_state = "not_started"
        elif today_record.clock_out_at is None:
            today_state = "working"
        else:
            today_state = "finished"

        start = today - timedelta(days=6)
        pending_dates, leave_dates = _pending_and_leave_dates(user, start, today - timedelta(days=1))
        recent = [
            _serialize_record(user, start + timedelta(days=i), pending_dates, leave_dates)
            for i in range((today - start).days)
        ]

        monthly = record_service.aggregate_monthly(user, today.strftime("%Y-%m"))
        policy = OvertimeLimitPolicy.objects.filter(is_default=True).first() or OvertimeLimitPolicy.objects.first()

        notifications = [
            {
                "id": str(n.id),
                "category": n.category,
                "title": n.title,
                "detail": n.body,
                "created_at": n.created_at.isoformat(),
                "read": n.read_at is not None,
            }
            for n in Notification.objects.filter(user=user)[:20]
        ]

        return Response(
            {
                "today": {
                    "date": today.isoformat(),
                    "state": today_state,
                    "clock_in_at": timezone.localtime(today_record.clock_in_at).strftime("%H:%M")
                    if today_record and today_record.clock_in_at
                    else None,
                    "clock_out_at": timezone.localtime(today_record.clock_out_at).strftime("%H:%M")
                    if today_record and today_record.clock_out_at
                    else None,
                },
                "recent": recent,
                "monthly_summary": {
                    "work_days": monthly.work_days,
                    "worked_hours": round(monthly.worked_minutes / 60, 1),
                    "overtime_hours": round(monthly.overtime_36_minutes / 60, 2),
                    "overtime_limit_hours": round((policy.monthly_limit_minutes if policy else 2700) / 60, 1),
                    "paid_leave_remaining": _leave_balance_for(user),
                },
                "notifications": notifications,
            }
        )


class MonthlyDetailView(APIView):
    """勤怠明細（日次一覧）と月次締め状態。設計書 第9章「勤怠明細・修正申請」。"""

    @extend_schema(summary="勤怠明細（月次）")
    def get(self, request: Request) -> Response:
        import calendar

        user = request.user
        year_month = request.query_params.get("ym") or timezone.localdate().strftime("%Y-%m")
        year, month = (int(p) for p in year_month.split("-"))
        last_day = calendar.monthrange(year, month)[1]
        start = timezone.datetime(year, month, 1).date()
        end = timezone.datetime(year, month, last_day).date()
        today = timezone.localdate()
        if end > today:
            end = today if today >= start else start

        pending_dates, leave_dates = _pending_and_leave_dates(user, start, end)
        days = [
            _serialize_record(user, start + timedelta(days=i), pending_dates, leave_dates)
            for i in range((end - start).days + 1)
        ]

        monthly = MonthlyAttendance.objects.filter(user=user, year_month=year_month).first()
        return Response(
            {
                "year_month": year_month,
                "status": monthly.status if monthly else "draft",
                "locked": bool(monthly and monthly.locked_at),
                "totals": {
                    "work_days": monthly.work_days if monthly else 0,
                    "worked_hours": round((monthly.worked_minutes if monthly else 0) / 60, 1),
                    "overtime_hours": round((monthly.overtime_36_minutes if monthly else 0) / 60, 2),
                },
                "days": days,
            }
        )


class MonthlySubmitView(APIView):
    """月次締め申請。本人が「この月の内容に相違ありません」と確定する（設計書 第5.4章）。"""

    @extend_schema(summary="月次締め申請")
    def post(self, request: Request) -> Response:
        year_month = request.data.get("year_month")
        if not year_month:
            return Response(
                {"code": "invalid", "message": "対象年月を指定してください。", "field_errors": {}}, status=400
            )
        monthly = record_service.submit_monthly(request.user, year_month)
        for admin in _admin_users():
            notify(
                admin,
                "approval",
                "月次勤怠の承認依頼",
                f"{request.user.name}さんから{year_month}分の月次確定申請が届いています。",
                "/approvals",
            )
        return Response({"year_month": monthly.year_month, "status": monthly.status})


class TeamStatusView(APIView):
    """他社員の出勤状況を確認する。既定は自分のグループ、`scope=all` で全社員に切り替える。"""

    @extend_schema(summary="出勤状況（グループ／全社員）")
    def get(self, request: Request) -> Response:
        from apps.accounts.models import User
        from apps.leave.models import LeaveRequest, LeaveRequestStatus

        viewer = request.user
        requested_scope = request.query_params.get("scope", "team")
        fallback_to_all = False

        if requested_scope != "all" and viewer.team_id is None:
            requested_scope = "all"
            fallback_to_all = True

        qs = User.objects.filter(is_active=True).select_related("team")
        scope = "team" if requested_scope != "all" else "all"
        if scope == "team":
            qs = qs.filter(team_id=viewer.team_id)

        today = timezone.localdate()
        records = {r.user_id: r for r in TimeRecord.objects.filter(user__in=qs, work_date=today)}
        on_leave_ids = set(
            LeaveRequest.objects.filter(
                user__in=qs,
                status=LeaveRequestStatus.APPROVED,
                start_date__lte=today,
                end_date__gte=today,
            ).values_list("user_id", flat=True)
        )

        members = []
        for user in qs.order_by("name"):
            record = records.get(user.id)
            if record is None or record.clock_in_at is None:
                state = "not_started"
            elif record.clock_out_at is None:
                state = "working"
            else:
                state = "finished"
            members.append(
                {
                    "id": user.id,
                    "name": user.name,
                    "team_name": user.team.name if user.team else None,
                    "is_admin": user.is_admin_role,
                    "state": state,
                    "clock_in_at": timezone.localtime(record.clock_in_at).strftime("%H:%M")
                    if record and record.clock_in_at
                    else None,
                    "clock_out_at": timezone.localtime(record.clock_out_at).strftime("%H:%M")
                    if record and record.clock_out_at
                    else None,
                    "on_leave": user.id in on_leave_ids,
                }
            )

        return Response(
            {
                "scope": scope,
                "fallback_to_all": fallback_to_all,
                "team_name": viewer.team.name if viewer.team else None,
                "members": members,
            }
        )


class PunchView(APIView):
    @extend_schema(request=PunchSerializer, summary="打刻")
    def post(self, request: Request) -> Response:
        def handle() -> Response:
            serializer = PunchSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            action = serializer.validated_data["action"]
            try:
                if action == "in":
                    record_service.clock_in(request.user)
                elif action == "out":
                    record_service.clock_out(request.user)
                elif action == "break_start":
                    record_service.start_break(request.user)
                else:
                    record_service.end_break(request.user)
            except record_service.MonthLockedError as exc:
                return Response({"code": "locked", "message": str(exc), "field_errors": {}}, status=409)
            except ValueError as exc:
                return Response({"code": "invalid", "message": str(exc), "field_errors": {}}, status=400)
            return Response(status=status.HTTP_204_NO_CONTENT)

        return with_idempotency(request, "attendance-punch", handle)


class CorrectionRequestListCreateView(APIView):
    @extend_schema(summary="打刻修正依頼の一覧")
    def get(self, request: Request) -> Response:
        qs = TimeCorrectionRequest.objects.filter(user=request.user)
        return Response(CorrectionRequestSerializer(qs, many=True).data)

    @extend_schema(request=CorrectionRequestCreateSerializer, summary="打刻修正を依頼する")
    def post(self, request: Request) -> Response:
        serializer = CorrectionRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        hh, mm = (int(p) for p in data["corrected_time"].split(":"))
        naive = datetime.combine(data["date"], datetime.min.time()).replace(hour=hh, minute=mm)
        aware = timezone.make_aware(naive)

        kwargs = {}
        if data["type"] == "clock_in":
            kwargs["requested_clock_in_at"] = aware
        else:
            kwargs["requested_clock_out_at"] = aware

        correction = TimeCorrectionRequest.objects.create(
            user=request.user, work_date=data["date"], reason=data["reason"], **kwargs
        )
        for admin in _admin_users():
            notify(
                admin,
                "approval",
                "打刻修正の承認依頼",
                f"{request.user.name}さんから {data['date']} の打刻修正依頼が届いています。",
                "/approvals",
            )
        return Response(CorrectionRequestSerializer(correction).data, status=201)


def _admin_users():
    from apps.accounts.models import Role, User

    return User.objects.filter(role=Role.ADMIN, is_active=True)


class AdminCorrectionApproveView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    @extend_schema(summary="打刻修正を承認")
    def post(self, request: Request, pk: int) -> Response:
        correction = _get_or_404(TimeCorrectionRequest, pk)
        correction.status = CorrectionStatus.APPROVED
        correction.reviewed_by = request.user
        correction.reviewed_at = timezone.now()
        correction.save(update_fields=["status", "reviewed_by", "reviewed_at"])
        record_service.apply_correction(correction)
        notify(correction.user, "approval", "打刻修正が承認されました", f"{correction.work_date} の打刻修正が承認されました。")
        record_audit(request, "correction_approve", "TimeCorrectionRequest", correction.id, after={"status": "approved"})
        return Response(status=204)


class AdminCorrectionRejectView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    @extend_schema(request=RejectSerializer, summary="打刻修正を差し戻す")
    def post(self, request: Request, pk: int) -> Response:
        serializer = RejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        correction = _get_or_404(TimeCorrectionRequest, pk)
        correction.status = CorrectionStatus.REJECTED
        correction.rejected_reason = serializer.validated_data["reason"]
        correction.reviewed_by = request.user
        correction.reviewed_at = timezone.now()
        correction.save(update_fields=["status", "rejected_reason", "reviewed_by", "reviewed_at"])
        notify(
            correction.user,
            "info",
            "打刻修正が差し戻されました",
            serializer.validated_data["reason"],
        )
        record_audit(
            request,
            "correction_reject",
            "TimeCorrectionRequest",
            correction.id,
            after={"status": "rejected", "reason": serializer.validated_data["reason"]},
        )
        return Response(status=204)


class AdminMonthlyApproveView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    @extend_schema(summary="月次勤怠を承認")
    def post(self, request: Request, pk: int) -> Response:
        monthly = _get_or_404(MonthlyAttendance, pk)
        record_service.approve_monthly(monthly, request.user)
        notify(monthly.user, "approval", "月次勤怠が承認されました", f"{monthly.year_month} 分の勤怠が承認されました。")
        record_audit(request, "monthly_approve", "MonthlyAttendance", monthly.id, after={"year_month": monthly.year_month})
        return Response(status=204)


class AdminMonthlyRejectView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    @extend_schema(summary="月次勤怠を差し戻す")
    def post(self, request: Request, pk: int) -> Response:
        monthly = _get_or_404(MonthlyAttendance, pk)
        record_service.reject_monthly(monthly)
        notify(monthly.user, "info", "月次勤怠が差し戻されました", f"{monthly.year_month} 分の勤怠が差し戻されました。")
        record_audit(request, "monthly_reject", "MonthlyAttendance", monthly.id, after={"year_month": monthly.year_month})
        return Response(status=204)


class AdminMonthlyReopenView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    @extend_schema(summary="月次勤怠を再オープン")
    def post(self, request: Request, pk: int) -> Response:
        monthly = _get_or_404(MonthlyAttendance, pk)
        record_service.reopen_monthly(monthly)
        return Response(status=204)


def _get_or_404(model, pk):
    from django.shortcuts import get_object_or_404

    return get_object_or_404(model, pk=pk)
