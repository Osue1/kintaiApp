from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.audit import record_audit
from apps.common.permissions import IsAdminRole
from apps.notifications.services import notify

from .models import LeaveConsumption, LeaveRequest, LeaveRequestStatus, LeaveType, PaidLeaveGrant
from .serializers import (
    LeaveRejectSerializer,
    LeaveRequestCreateSerializer,
    LeaveRequestSerializer,
    LeaveTypeSerializer,
)
from .services.balance import GrantLot, InsufficientBalanceError, plan_consumption, remaining_days


def _grant_lots(user, *, for_update: bool = False) -> tuple[GrantLot, ...]:
    """付与ロット一覧を取得する。

    for_update=True の場合、付与ロット行を SELECT ... FOR UPDATE でロックする。
    同一利用者の複数の休暇申請が別々の承認リクエストとして並行処理されると、
    どちらも「消化前」の残日数スナップショットを読んで消化計画を立ててしまい、
    合計すると残日数を超えて消化（二重消費）してしまう恐れがあるため、
    残日数を実際に消費する承認処理からはロックを取って呼び出すこと。
    """
    grants = PaidLeaveGrant.objects.filter(user=user).prefetch_related("consumptions")
    if for_update:
        # consumptions 側にも将来 FOR UPDATE が必要になった場合に備え、まずは
        # 付与ロット本体をロックして「同時に2つの承認が同じロットを対象に
        # 消化計画を立てる」状態を防ぐ（PostgreSQL の行ロックはロックした
        # トランザクションが commit/rollback するまで後続の SELECT FOR UPDATE を待たせる）。
        grants = grants.select_for_update()
    return tuple(
        GrantLot(
            id=g.id,
            days=g.days,
            expires_on=g.expires_on,
            consumed=sum((c.days for c in g.consumptions.all()), Decimal("0")),
        )
        for g in grants
    )


def _latest_grant(user) -> PaidLeaveGrant | None:
    return PaidLeaveGrant.objects.filter(user=user).order_by("-granted_on").first()


class LeaveTypesView(APIView):
    @extend_schema(summary="休暇種類の一覧")
    def get(self, request: Request) -> Response:
        types = LeaveType.objects.filter(is_active=True)
        return Response(LeaveTypeSerializer(types, many=True).data)


class LeaveBalanceView(APIView):
    @extend_schema(summary="有給休暇の残日数")
    def get(self, request: Request) -> Response:
        user = request.user
        today = timezone.localdate()
        lots = _grant_lots(user)
        remaining = remaining_days(lots, as_of=today)
        latest = _latest_grant(user)
        paid_total = latest.days if latest else Decimal("0")
        paid_used = sum((lot.consumed for lot in lots if lot.expires_on >= today), Decimal("0"))
        carry_over = sum(
            (lot.remaining for lot in lots if lot.expires_on >= today and latest and lot.id != latest.id),
            Decimal("0"),
        )

        next_grant = None
        policy = latest.policy if latest else None
        if policy and user.hire_date:
            from .services.grant import GrantRuleRow, months_between, resolve_grant_days

            rules = tuple(
                GrantRuleRow(r.months_of_service, r.granted_days, r.prorated_weekly_days)
                for r in policy.grant_rules.filter(prorated_weekly_days__isnull=True)
            )
            current_months = months_between(user.hire_date, today)
            upcoming = sorted({r.months_of_service for r in rules if r.months_of_service > current_months})
            if upcoming:
                next_months = upcoming[0]
                next_date = _add_months(user.hire_date, next_months)
                next_days = resolve_grant_days(rules, next_months)
                next_grant = {"date": next_date.isoformat(), "days": float(next_days or 0)}

        mandatory = {"used": 0.0, "required": 0, "deadline": today.isoformat()}
        if latest and latest.days >= 10:
            window_end = _add_months(latest.granted_on, 12)
            used = LeaveRequest.objects.filter(
                user=user,
                leave_type__counts_toward_mandatory_five=True,
                status=LeaveRequestStatus.APPROVED,
                start_date__gte=latest.granted_on,
                start_date__lt=window_end,
            )
            total_used = sum((r.days for r in used), Decimal("0"))
            mandatory = {"used": float(total_used), "required": 5, "deadline": window_end.isoformat()}

        others = []
        year_start = date(today.year, 1, 1)
        for lt in LeaveType.objects.filter(is_active=True, counts_toward_mandatory_five=False):
            used = LeaveRequest.objects.filter(
                user=user,
                leave_type=lt,
                status=LeaveRequestStatus.APPROVED,
                start_date__gte=year_start,
            )
            used_days = sum((r.days for r in used), Decimal("0"))
            remaining_for_type = float(lt.annual_limit_days - used_days) if lt.annual_limit_days is not None else None
            others.append({"type_id": str(lt.id), "type_name": lt.name, "remaining": remaining_for_type})

        return Response(
            {
                "paid_total": float(paid_total),
                "paid_used": float(paid_used),
                "paid_remaining": float(remaining),
                "carry_over": float(carry_over),
                "next_grant": next_grant or {"date": today.isoformat(), "days": 0},
                "mandatory_five_days": mandatory,
                "others": others,
            }
        )


def _add_months(d: date, months: int) -> date:
    total = d.month - 1 + months
    year = d.year + total // 12
    month = total % 12 + 1
    import calendar

    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


class LeaveRequestListCreateView(APIView):
    @extend_schema(summary="休暇申請の一覧")
    def get(self, request: Request) -> Response:
        qs = LeaveRequest.objects.filter(user=request.user).select_related("leave_type")
        return Response(LeaveRequestSerializer(qs, many=True).data)

    @extend_schema(request=LeaveRequestCreateSerializer, summary="休暇を申請する")
    def post(self, request: Request) -> Response:
        serializer = LeaveRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        leave_type = data["leave_type"]
        days = Decimal("1") if data["unit"] == "full" else Decimal("0.5")
        if data["unit"] == "full":
            days = Decimal((data["end_date"] - data["start_date"]).days + 1)

        if leave_type.is_paid and leave_type.counts_toward_mandatory_five:
            lots = _grant_lots(request.user)
            if remaining_days(lots, as_of=timezone.localdate()) < days:
                return Response(
                    {"code": "insufficient_balance", "message": "有給休暇の残日数が不足しています。", "field_errors": {}},
                    status=400,
                )

        leave_request = LeaveRequest.objects.create(
            user=request.user,
            leave_type=leave_type,
            start_date=data["start_date"],
            end_date=data["end_date"],
            unit=data["unit"],
            days=days,
            reason=data.get("reason", ""),
        )
        for admin in _admin_users():
            notify(
                admin,
                "approval",
                "休暇申請の承認依頼",
                f"{request.user.name}さんから{leave_type.name}の申請が届いています。",
                "/approvals",
            )
        return Response(LeaveRequestSerializer(leave_request).data, status=201)


def _admin_users():
    from apps.accounts.models import Role, User

    return User.objects.filter(role=Role.ADMIN, is_active=True)


class AdminLeaveApproveView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    @extend_schema(summary="休暇申請を承認")
    @transaction.atomic
    def post(self, request: Request, pk: int) -> Response:
        from django.shortcuts import get_object_or_404

        # 対象の申請行自体をロックし、承認処理中は他のリクエスト（同じ申請への
        # 二重承認クリック・承認と差し戻しの競合など）が状態を読めないようにする。
        leave_request = get_object_or_404(LeaveRequest.objects.select_for_update(), pk=pk)
        if leave_request.status != LeaveRequestStatus.PENDING:
            # 既に承認・差し戻し済みの申請。ここで弾かないと、承認ボタンの
            # 二重クリックや2人の管理者が同時に操作した場合に有給消化明細が
            # 二重に作成されてしまう（残日数の二重消費）。
            return Response(
                {"code": "already_processed", "message": "この申請は既に処理済みです。", "field_errors": {}},
                status=409,
            )

        if leave_request.leave_type.is_paid and leave_request.leave_type.counts_toward_mandatory_five:
            # for_update=True: 同じ利用者の別の申請が同時に承認されても、
            # 付与ロットの残日数を正しく直列化して二重消費を防ぐ。
            lots = _grant_lots(leave_request.user, for_update=True)
            try:
                plan = plan_consumption(lots, leave_request.days, as_of=timezone.localdate())
            except InsufficientBalanceError as exc:
                return Response({"code": "insufficient_balance", "message": str(exc), "field_errors": {}}, status=409)
            for grant_id, consumed_days in plan.allocations:
                LeaveConsumption.objects.create(
                    grant_id=grant_id, leave_request=leave_request, days=consumed_days
                )

        if leave_request.leave_type.requires_period:
            from .models import LeaveAbsencePeriod

            LeaveAbsencePeriod.objects.get_or_create(
                user=leave_request.user,
                leave_type=leave_request.leave_type,
                leave_request=leave_request,
                defaults={"start_date": leave_request.start_date, "end_date": leave_request.end_date},
            )

        leave_request.status = LeaveRequestStatus.APPROVED
        leave_request.reviewed_by = request.user
        leave_request.reviewed_at = timezone.now()
        leave_request.save(update_fields=["status", "reviewed_by", "reviewed_at"])
        notify(
            leave_request.user,
            "approval",
            "休暇申請が承認されました",
            f"{leave_request.start_date} の{leave_request.leave_type.name}が承認されました。",
        )
        record_audit(request, "leave_approve", "LeaveRequest", leave_request.id, after={"status": "approved"})
        return Response(status=204)


class AdminLeaveRejectView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    @extend_schema(request=LeaveRejectSerializer, summary="休暇申請を差し戻す")
    @transaction.atomic
    def post(self, request: Request, pk: int) -> Response:
        from django.shortcuts import get_object_or_404

        serializer = LeaveRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # 承認処理と同様に行ロック＋状態チェックを行う。ロックしないと、
        # 承認処理と差し戻し処理が同時に走った場合に「有給は消化済みなのに
        # ステータスは差し戻し」という矛盾した状態になり得る。
        leave_request = get_object_or_404(LeaveRequest.objects.select_for_update(), pk=pk)
        if leave_request.status != LeaveRequestStatus.PENDING:
            return Response(
                {"code": "already_processed", "message": "この申請は既に処理済みです。", "field_errors": {}},
                status=409,
            )
        leave_request.status = LeaveRequestStatus.REJECTED
        leave_request.rejected_reason = serializer.validated_data["reason"]
        leave_request.reviewed_by = request.user
        leave_request.reviewed_at = timezone.now()
        leave_request.save(update_fields=["status", "rejected_reason", "reviewed_by", "reviewed_at"])
        notify(leave_request.user, "info", "休暇申請が差し戻されました", serializer.validated_data["reason"])
        record_audit(
            request,
            "leave_reject",
            "LeaveRequest",
            leave_request.id,
            after={"status": "rejected", "reason": serializer.validated_data["reason"]},
        )
        return Response(status=204)


class LeaveLedgerView(APIView):
    """年次有給休暇管理簿（設計書 第9章）。基準日ごとに時季・日数を一覧化する。"""

    permission_classes = [IsAuthenticated, IsAdminRole]

    @extend_schema(summary="年次有給休暇管理簿")
    def get(self, request: Request) -> Response:
        from django.shortcuts import get_object_or_404

        from apps.accounts.models import User

        from .services.ledger import build_ledger

        user = get_object_or_404(User, pk=request.query_params.get("user_id"))
        rows = build_ledger(user)
        return Response(
            {
                "employee": {"id": user.id, "name": user.name, "hire_date": user.hire_date},
                "grants": [
                    {
                        "granted_on": r.granted_on,
                        "days": float(r.days),
                        "expires_on": r.expires_on,
                        "consumed": float(r.consumed),
                        "remaining": float(r.remaining),
                        "is_expired": r.is_expired,
                        "consumptions": [
                            {"date_label": c.date_label, "days": float(c.days), "leave_type_name": c.leave_type_name}
                            for c in r.consumptions
                        ],
                    }
                    for r in rows
                ],
            }
        )


class LeaveLedgerPdfView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    @extend_schema(summary="年次有給休暇管理簿PDF")
    def get(self, request: Request) -> Response:
        from django.http import HttpResponse
        from django.shortcuts import get_object_or_404
        from django.template.loader import render_to_string
        from weasyprint import HTML

        from apps.accounts.models import Company, User

        from .services.ledger import build_ledger

        user = get_object_or_404(User, pk=request.query_params.get("user_id"))
        rows = build_ledger(user)
        html = render_to_string(
            "leave/ledger.html", {"employee": user, "company": Company.get_solo(), "grants": rows}
        )
        pdf_bytes = HTML(string=html).write_pdf()
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="leave_ledger_{user.id}.pdf"'
        return response
