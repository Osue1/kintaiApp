"""ローカル動作確認用のデモデータを投入する（冪等ではあるが再実行は基本不要）。

`seed_initial_data` が会社共通のマスタを作るのに対し、こちらは「導入からしばらく
運用している状態」を再現する—社員・外注先・打刻履歴・休暇消化・請求実績など。
本番投入には使わない。
"""
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role, Team, User
from apps.attendance.models import MonthlyAttendance, MonthlyStatus, TimeCorrectionRequest
from apps.attendance.services import records as record_service
from apps.contractors.models import Contractor, ContractorRate, ContractorWorkRecord
from apps.leave.models import (
    LeaveConsumption,
    LeaveRequest,
    LeaveRequestStatus,
    LeaveType,
    PaidLeaveGrant,
    PaidLeavePolicy,
)
from apps.notifications.services import notify


def _make_aware(d: date, hh: int, mm: int) -> datetime:
    return timezone.make_aware(datetime.combine(d, time(hh, mm)))


def _business_days_back(from_date: date, count: int) -> list[date]:
    days: list[date] = []
    cursor = from_date
    while len(days) < count:
        cursor -= timedelta(days=1)
        if cursor.weekday() < 5:
            days.append(cursor)
    return list(reversed(days))


class Command(BaseCommand):
    help = "ローカル確認用のデモデータ（社員・外注先・打刻履歴・休暇・請求実績）を投入する"

    @transaction.atomic
    def handle(self, *args, **options) -> None:
        self._create_users()
        self._create_leave_history()
        self._create_attendance_history()
        self._create_contractors()
        self.stdout.write(self.style.SUCCESS("デモデータの投入が完了しました。"))

    def _create_users(self) -> None:
        from apps.attendance.models import WorkPattern

        pattern = WorkPattern.objects.filter(is_default=True).first()
        policy = PaidLeavePolicy.objects.filter(is_default=True).first()
        today = timezone.localdate()

        if not User.objects.filter(email="admin@example.com").exists():
            User.objects.create_superuser(
                email="admin@example.com", password="admin12345678", name="管理者"
            )
            self.stdout.write("管理者アカウント: admin@example.com / admin12345678")

        dev_team, _ = Team.objects.get_or_create(name="開発チーム")
        sales_team, _ = Team.objects.get_or_create(name="営業チーム")

        employees = [
            ("sato@example.com", "佐藤花子", today - timedelta(days=400), dev_team),
            ("suzuki@example.com", "鈴木一郎", today - timedelta(days=280), dev_team),
            ("takahashi@example.com", "高橋美咲", today - timedelta(days=650), dev_team),
            ("tanaka@example.com", "田中健太", today - timedelta(days=340), sales_team),
            ("watanabe@example.com", "渡辺さくら", today - timedelta(days=310), sales_team),
            ("ito@example.com", "伊藤大輔", today - timedelta(days=900), sales_team),
        ]
        for email, name, hire_date, team in employees:
            existing = User.objects.filter(email=email).first()
            if existing:
                if existing.team_id is None:
                    existing.team = team
                    existing.save(update_fields=["team"])
                continue
            User.objects.create_user(
                email=email,
                password="employee12345",
                name=name,
                role=Role.EMPLOYEE,
                work_pattern=pattern,
                leave_policy=policy,
                team=team,
                hire_date=hire_date,
            )
        self.stdout.write("正社員アカウント: <email> / employee12345（例: sato@example.com）")
        self.stdout.write("グループ: 開発チーム（佐藤・鈴木・高橋） / 営業チーム（田中・渡辺・伊藤）")

    def _create_leave_history(self) -> None:
        today = timezone.localdate()
        paid = LeaveType.objects.get(name="年次有給休暇")
        compensatory = LeaveType.objects.get(name="代休")
        policy = PaidLeavePolicy.objects.filter(is_default=True).first()

        for user in User.objects.filter(role=Role.EMPLOYEE):
            if PaidLeaveGrant.objects.filter(user=user).exists():
                continue
            # 前年度分（繰越の元）と当年度分の2ロットを持たせ、繰越表示を再現する。
            last_grant_date = today.replace(month=4, day=1)
            if last_grant_date > today:
                last_grant_date = last_grant_date.replace(year=last_grant_date.year - 1)
            prev_grant_date = last_grant_date.replace(year=last_grant_date.year - 1)

            prev_grant = PaidLeaveGrant.objects.create(
                user=user,
                policy=policy,
                granted_on=prev_grant_date,
                days=Decimal("20"),
                expires_on=prev_grant_date.replace(year=prev_grant_date.year + 2),
                source_note="デモ初期付与（前年度）",
            )
            PaidLeaveGrant.objects.create(
                user=user,
                policy=policy,
                granted_on=last_grant_date,
                days=Decimal("20"),
                expires_on=last_grant_date.replace(year=last_grant_date.year + 2),
                source_note="デモ初期付与（当年度）",
            )

            # 過去の承認済み休暇（前年度ロットから消化）
            approved_leave = LeaveRequest.objects.create(
                user=user,
                leave_type=paid,
                start_date=today - timedelta(days=20),
                end_date=today - timedelta(days=20),
                unit="full",
                days=Decimal("1"),
                status=LeaveRequestStatus.APPROVED,
                reviewed_at=timezone.now(),
            )
            LeaveConsumption.objects.create(grant=prev_grant, leave_request=approved_leave, days=Decimal("1"))

            LeaveRequest.objects.create(
                user=user,
                leave_type=compensatory,
                start_date=today - timedelta(days=12),
                end_date=today - timedelta(days=12),
                unit="half_pm",
                days=Decimal("0.5"),
                status=LeaveRequestStatus.APPROVED,
                reviewed_at=timezone.now(),
            )

            # 申請中（将来日）
            LeaveRequest.objects.create(
                user=user,
                leave_type=paid,
                start_date=today + timedelta(days=9),
                end_date=today + timedelta(days=10),
                unit="full",
                days=Decimal("2"),
                reason="帰省のため",
                status=LeaveRequestStatus.PENDING,
            )
            notify(user, "reminder", "有給休暇の取得状況をご確認ください", "年5日の取得義務まで残りわずかです。")

    def _create_attendance_history(self) -> None:
        today = timezone.localdate()
        business_days = _business_days_back(today, 20)

        for i, user in enumerate(User.objects.filter(role=Role.EMPLOYEE)):
            for j, d in enumerate(business_days):
                clock_out_hour = 18
                clock_out_min = 5
                # 田中健太・伊藤大輔は残業多めにして36協定アラートを再現する
                if user.name in ("田中健太", "伊藤大輔") and j % 2 == 0:
                    clock_out_hour, clock_out_min = 21, 30
                record_service.clock_in(user, at=_make_aware(d, 9, 0 + (i % 5)))
                record_service.clock_out(user, at=_make_aware(d, clock_out_hour, clock_out_min))

            aggregate = record_service.aggregate_monthly(user, today.strftime("%Y-%m"))
            self.stdout.write(f"打刻履歴: {user.name} 実働{aggregate.worked_minutes}分")

            last_month = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
            monthly, _ = MonthlyAttendance.objects.get_or_create(
                user=user,
                year_month=last_month,
                defaults={"status": MonthlyStatus.APPROVED, "locked_at": timezone.now()},
            )
            if monthly.status != MonthlyStatus.APPROVED:
                monthly.status = MonthlyStatus.APPROVED
                monthly.locked_at = timezone.now()
                monthly.save(update_fields=["status", "locked_at"])

        # 打刻修正依頼のサンプル
        first_employee = User.objects.filter(role=Role.EMPLOYEE).first()
        if first_employee and not TimeCorrectionRequest.objects.filter(user=first_employee).exists():
            TimeCorrectionRequest.objects.create(
                user=first_employee,
                work_date=business_days[-1],
                requested_clock_out_at=_make_aware(business_days[-1], 19, 45),
                reason="客先対応で退勤打刻を忘れていました。",
            )

    def _create_contractors(self) -> None:
        today = timezone.localdate()
        last_month = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")

        specs = [
            {
                "name": "合同会社ノースデザイン",
                "email": "contact@north-design.example.com",
                "rate_type": "hourly",
                "rate_amount": Decimal("4500"),
                "closing_day": 31,
                "payment_month_offset": 1,
                "payment_day": 10,
                "record": {"hours": Decimal("62.5")},
            },
            {
                "name": "山本圭（フリーランス）",
                "email": "kei.yamamoto@example.com",
                "rate_type": "daily",
                "rate_amount": Decimal("28000"),
                "closing_day": 20,
                "payment_month_offset": 1,
                "payment_day": 5,
                "record": {"days": Decimal("14")},
            },
            {
                "name": "株式会社ライトブリッジ",
                "email": "info@lightbridge.example.com",
                "rate_type": "fixed",
                "rate_amount": Decimal("350000"),
                "closing_day": 31,
                "payment_month_offset": 1,
                "payment_day": 15,
                "record": None,
            },
        ]

        for spec in specs:
            contractor, created = Contractor.objects.get_or_create(
                name=spec["name"],
                defaults={
                    "email": spec["email"],
                    "closing_day": spec["closing_day"],
                    "payment_month_offset": spec["payment_month_offset"],
                    "payment_day": spec["payment_day"],
                },
            )
            if created:
                ContractorRate.objects.create(
                    contractor=contractor,
                    rate_type=spec["rate_type"],
                    rate_amount=spec["rate_amount"],
                    effective_from=today - timedelta(days=180),
                )
            if spec["record"]:
                ContractorWorkRecord.objects.get_or_create(
                    contractor=contractor,
                    year_month=last_month,
                    defaults={**spec["record"], "note": ""},
                )
        self.stdout.write("外注先: 3件登録")
