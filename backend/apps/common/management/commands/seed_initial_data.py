"""環境作成直後に投入する初期データ。

導入時に管理者が空のマスタを埋める作業を発生させないため、
法定どおりの設定で最初から動く状態にして引き渡す（追補 第8.1章）。

スキーマが固まったら、この処理はデータマイグレーションへ移す。
そうすればデプロイするだけで全環境に反映される（追補 第7.1章）。
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Company
from apps.attendance.models import BreakMode, WorkPattern
from apps.compliance.models import OvertimeLimitPolicy
from apps.leave.models import LeaveType, PaidLeaveGrantRule, PaidLeavePolicy

WORK_PATTERNS = [
    {
        "name": "標準（週休2日・休憩は自動控除）",
        "break_mode": BreakMode.AUTO_DEDUCT,
        "break_rules": [{"over": 360, "deduct": 45}, {"over": 480, "deduct": 60}],
        "scheduled_minutes": 480,
        "holiday_dow": [0, 6],
        "statutory_holiday_dow": 0,
        "is_default": True,
    },
    {
        "name": "標準（週休2日・休憩を実打刻）",
        "break_mode": BreakMode.PUNCH,
        "break_rules": [],
        "scheduled_minutes": 480,
        "holiday_dow": [0, 6],
        "statutory_holiday_dow": 0,
        "is_default": False,
    },
]

# 労基法39条の法定テーブル（設計書 第6.1章）。管理者はこの行を自由に追加・編集・削除できる。
STATUTORY_GRANT_TABLE = [
    (6, Decimal("10")),
    (18, Decimal("11")),
    (30, Decimal("12")),
    (42, Decimal("14")),
    (54, Decimal("16")),
    (66, Decimal("18")),
    (78, Decimal("20")),
]

LEAVE_TYPES = [
    {
        "name": "年次有給休暇",
        "is_paid": True,
        "supports_half_day": True,
        "requires_reason": False,
        "counts_toward_mandatory_five": True,
        "display_order": 1,
    },
    {
        "name": "慶弔休暇",
        "is_paid": True,
        "supports_half_day": False,
        "requires_reason": True,
        "annual_limit_days": Decimal("5"),
        "display_order": 2,
    },
    {
        "name": "代休",
        "is_paid": True,
        "supports_half_day": True,
        "requires_reason": False,
        "display_order": 3,
    },
    {
        "name": "欠勤",
        "is_paid": False,
        "supports_half_day": True,
        "requires_reason": True,
        "display_order": 4,
    },
    {
        "name": "産前産後休業",
        "is_paid": False,
        "supports_half_day": False,
        "requires_reason": False,
        "requires_period": True,
        "display_order": 5,
    },
    {
        "name": "育児介護休業",
        "is_paid": False,
        "supports_half_day": False,
        "requires_reason": False,
        "requires_period": True,
        "display_order": 6,
    },
]


class Command(BaseCommand):
    help = "会社設定・勤務体系・休暇種類・有給ポリシー・36協定ポリシーの初期データを投入する（冪等）"

    @transaction.atomic
    def handle(self, *args, **options) -> None:
        company = Company.get_solo()
        if company.name == "未設定":
            company.name = "サンプル株式会社"
            company.address = "東京都千代田区丸の内1-1-1"
            company.representative = "代表取締役 山田太郎"
            company.invoice_reg_no = "T1234567890123"
            company.save()
        self.stdout.write(f"会社設定: {company.name}")

        for spec in WORK_PATTERNS:
            obj, created = WorkPattern.objects.get_or_create(name=spec["name"], defaults=spec)
            self.stdout.write(f"勤務体系[{'作成' if created else '既存'}]: {obj.name}")

        for spec in LEAVE_TYPES:
            obj, created = LeaveType.objects.get_or_create(name=spec["name"], defaults=spec)
            self.stdout.write(f"休暇種類[{'作成' if created else '既存'}]: {obj.name}")

        policy, created = PaidLeavePolicy.objects.get_or_create(
            name="標準（法定どおり）",
            defaults={
                "grant_method": "hire_date",
                "carryover_limit_days": None,
                "expiry_years": 2,
                "allow_half_day": True,
                "required_attendance_rate": Decimal("0.800"),
                "is_default": True,
            },
        )
        self.stdout.write(f"有給ポリシー[{'作成' if created else '既存'}]: {policy.name}")
        for months, days in STATUTORY_GRANT_TABLE:
            PaidLeaveGrantRule.objects.get_or_create(
                policy=policy,
                months_of_service=months,
                prorated_weekly_days=None,
                defaults={"granted_days": days},
            )

        overtime_policy, created = OvertimeLimitPolicy.objects.get_or_create(
            name="標準（36協定）",
            defaults={
                "monthly_limit_minutes": 45 * 60,
                "annual_limit_minutes": 360 * 60,
                "warning_threshold_percent": 80,
                "special_clause_enabled": True,
                "special_annual_limit_minutes": 720 * 60,
                "special_monthly_limit_minutes": 100 * 60,
                "special_monthly_over_limit_max_times": 6,
                "is_default": True,
            },
        )
        self.stdout.write(f"36協定ポリシー[{'作成' if created else '既存'}]: {overtime_policy.name}")

        self.stdout.write(self.style.SUCCESS("初期データの投入が完了しました。"))
