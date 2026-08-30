from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.common.models import TimeStampedModel


class LeaveUnit(models.TextChoices):
    FULL = "full", "全日"
    HALF_AM = "half_am", "午前半休"
    HALF_PM = "half_pm", "午後半休"


class LeaveType(TimeStampedModel):
    """休暇種類マスタ。管理者が追加・編集する（設計書 第6.4章）。"""

    name = models.CharField("名称", max_length=60)
    is_paid = models.BooleanField("有給", default=True)
    supports_half_day = models.BooleanField("半日取得可", default=False)
    requires_reason = models.BooleanField("理由必須", default=False)
    annual_limit_days = models.DecimalField(
        "年間上限日数", max_digits=5, decimal_places=1, null=True, blank=True, help_text="空欄は上限なし"
    )
    requires_period = models.BooleanField(
        "期間管理", default=False, help_text="産休・育休など。ONの場合は leave_absence_period を作る"
    )
    counts_toward_mandatory_five = models.BooleanField(
        "年5日取得義務の対象", default=False, help_text="年次有給休暇のみ ON にする"
    )
    is_active = models.BooleanField("有効", default=True)
    display_order = models.PositiveIntegerField("表示順", default=0)

    class Meta:
        verbose_name = verbose_name_plural = "休暇種類"
        ordering = ["display_order", "id"]

    def __str__(self) -> str:
        return self.name


class GrantMethod(models.TextChoices):
    HIRE_DATE = "hire_date", "入社日基準"
    UNIFORM = "uniform", "一斉付与"


class PaidLeavePolicy(TimeStampedModel):
    """有給の付与方式・繰越・失効ルール（設計書 第6.1章）。"""

    name = models.CharField("名称", max_length=60)
    grant_method = models.CharField(
        "付与方式", max_length=10, choices=GrantMethod.choices, default=GrantMethod.HIRE_DATE
    )
    uniform_grant_month = models.PositiveSmallIntegerField(
        "一斉付与月", null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    uniform_grant_day = models.PositiveSmallIntegerField(
        "一斉付与日", null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(31)]
    )
    carryover_limit_days = models.DecimalField(
        "繰越上限日数", max_digits=5, decimal_places=1, null=True, blank=True, help_text="空欄は無制限"
    )
    expiry_years = models.PositiveSmallIntegerField("失効年数", default=2)
    allow_half_day = models.BooleanField("半日取得可", default=True)
    required_attendance_rate = models.DecimalField(
        "付与に必要な出勤率", max_digits=4, decimal_places=3, default=0.800
    )
    is_default = models.BooleanField("新規ユーザーの初期割当", default=False)

    class Meta:
        verbose_name = verbose_name_plural = "有給ポリシー"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class PaidLeaveGrantRule(models.Model):
    """勤続月数 → 付与日数のテーブル（設計書 第6.1章）。法定テーブルは初期テンプレートとして投入。"""

    policy = models.ForeignKey(
        PaidLeavePolicy, verbose_name="ポリシー", on_delete=models.CASCADE, related_name="grant_rules"
    )
    months_of_service = models.PositiveIntegerField("勤続月数")
    granted_days = models.DecimalField("付与日数", max_digits=5, decimal_places=1)
    prorated_weekly_days = models.PositiveSmallIntegerField(
        "比例付与の週所定労働日数区分", null=True, blank=True, help_text="空欄はフルタイム"
    )

    class Meta:
        verbose_name = verbose_name_plural = "有給付与テーブル"
        ordering = ["policy", "prorated_weekly_days", "months_of_service"]
        constraints = [
            models.UniqueConstraint(
                fields=["policy", "months_of_service", "prorated_weekly_days"],
                name="uniq_grant_rule_policy_months_prorated",
            )
        ]

    def __str__(self) -> str:
        return f"{self.policy} {self.months_of_service}ヶ月→{self.granted_days}日"


class PaidLeaveGrant(models.Model):
    """付与実績1件＝1ロット。残日数はこのロットと消化明細から計算する（設計書 第6.2章）。"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="利用者", on_delete=models.CASCADE, related_name="paid_leave_grants"
    )
    policy = models.ForeignKey(
        PaidLeavePolicy, verbose_name="ポリシー", on_delete=models.PROTECT, related_name="grants"
    )
    granted_on = models.DateField("付与日")
    days = models.DecimalField("付与日数", max_digits=5, decimal_places=1)
    expires_on = models.DateField("失効日")
    source_note = models.CharField("備考", max_length=120, blank=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)

    class Meta:
        verbose_name = verbose_name_plural = "有給付与ロット"
        ordering = ["expires_on"]

    def __str__(self) -> str:
        return f"{self.user} {self.granted_on} +{self.days}日"


class LeaveRequestStatus(models.TextChoices):
    PENDING = "pending", "承認待ち"
    APPROVED = "approved", "承認済み"
    REJECTED = "rejected", "差し戻し"
    CANCELLED = "cancelled", "取消"


class LeaveRequest(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="利用者", on_delete=models.CASCADE, related_name="leave_requests"
    )
    leave_type = models.ForeignKey(
        LeaveType, verbose_name="休暇種類", on_delete=models.PROTECT, related_name="requests"
    )
    start_date = models.DateField("開始日")
    end_date = models.DateField("終了日")
    unit = models.CharField("単位", max_length=10, choices=LeaveUnit.choices, default=LeaveUnit.FULL)
    days = models.DecimalField("日数", max_digits=5, decimal_places=1)
    reason = models.CharField("理由", max_length=300, blank=True)
    status = models.CharField(
        "状態", max_length=20, choices=LeaveRequestStatus.choices, default=LeaveRequestStatus.PENDING
    )
    is_statutory_designation = models.BooleanField(
        "時季指定", default=False, help_text="年5日取得義務の会社時季指定に該当する場合 ON"
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="承認者",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    reviewed_at = models.DateTimeField("承認日時", null=True, blank=True)
    rejected_reason = models.CharField("差し戻し理由", max_length=300, blank=True)

    class Meta:
        verbose_name = verbose_name_plural = "休暇申請"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user} {self.leave_type} {self.start_date}"


class LeaveConsumption(models.Model):
    """どの付与ロットから何日消化したかの明細。残日数と失効判定の根拠（設計書 第6.2章）。"""

    grant = models.ForeignKey(
        PaidLeaveGrant, verbose_name="付与ロット", on_delete=models.CASCADE, related_name="consumptions"
    )
    leave_request = models.ForeignKey(
        LeaveRequest, verbose_name="休暇申請", on_delete=models.CASCADE, related_name="consumptions"
    )
    days = models.DecimalField("消化日数", max_digits=5, decimal_places=1)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)

    class Meta:
        verbose_name = verbose_name_plural = "有給消化明細"

    def __str__(self) -> str:
        return f"{self.grant} -{self.days}日"


class LeaveAbsencePeriod(TimeStampedModel):
    """産休・育休・介護休業の期間管理。期間中は勤怠集計対象外（設計書 第5.3章）。"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="利用者", on_delete=models.CASCADE, related_name="absence_periods"
    )
    leave_type = models.ForeignKey(
        LeaveType, verbose_name="休暇種類", on_delete=models.PROTECT, related_name="absence_periods"
    )
    start_date = models.DateField("開始日")
    end_date = models.DateField("終了予定日", null=True, blank=True)
    leave_request = models.ForeignKey(
        LeaveRequest,
        verbose_name="関連申請",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="absence_periods",
    )

    class Meta:
        verbose_name = verbose_name_plural = "産休・育休等の期間"
        ordering = ["-start_date"]

    def __str__(self) -> str:
        return f"{self.user} {self.leave_type} {self.start_date}〜{self.end_date or ''}"

    def covers(self, date) -> bool:
        if date < self.start_date:
            return False
        return self.end_date is None or date <= self.end_date
