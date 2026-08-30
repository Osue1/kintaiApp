from django.db import models

from apps.common.models import TimeStampedModel


class OvertimeLimitPolicy(TimeStampedModel):
    """36協定の上限値。上限は管理者が設定できる（設計書 第7章）。"""

    name = models.CharField("名称", max_length=60)
    monthly_limit_minutes = models.PositiveIntegerField("月間上限（分）", default=2700, help_text="既定45時間")
    annual_limit_minutes = models.PositiveIntegerField("年間上限（分）", default=21600, help_text="既定360時間")
    warning_threshold_percent = models.PositiveSmallIntegerField("警告閾値（％）", default=80)
    special_clause_enabled = models.BooleanField("特別条項あり", default=False)
    special_annual_limit_minutes = models.PositiveIntegerField(
        "特別条項時 年間上限（分）", default=43200, help_text="既定720時間"
    )
    special_monthly_limit_minutes = models.PositiveIntegerField(
        "特別条項時 単月上限（分・未満）", default=6000, help_text="既定100時間未満"
    )
    special_monthly_over_limit_max_times = models.PositiveSmallIntegerField(
        "月45時間超が許される回数/年", default=6
    )
    is_default = models.BooleanField("既定ポリシー", default=False)

    class Meta:
        verbose_name = verbose_name_plural = "36協定ポリシー"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class AlertType(models.TextChoices):
    PAID_LEAVE_FIVE_DAYS = "paid_leave_five_days", "年5日有給未取得"
    OVERTIME_MONTHLY = "overtime_monthly", "月間残業上限"
    OVERTIME_ANNUAL = "overtime_annual", "年間残業上限"
    OVERTIME_LANDING_FORECAST = "overtime_landing_forecast", "残業 着地見込み"
    OVERTIME_MULTI_MONTH_AVG = "overtime_multi_month_avg", "残業 複数月平均"
    OVERTIME_MONTHLY_OVER_COUNT = "overtime_monthly_over_count", "月45時間超の回数"


class AlertSeverity(models.TextChoices):
    WARNING = "warning", "注意"
    CRITICAL = "critical", "重大"
    VIOLATION = "violation", "違反"


class Alert(models.Model):
    """有給5日・36協定のアラート（設計書 第6.3章・第7章）。"""

    user = models.ForeignKey(
        "accounts.User", verbose_name="対象者", on_delete=models.CASCADE, related_name="alerts"
    )
    alert_type = models.CharField("種別", max_length=30, choices=AlertType.choices)
    target_period = models.CharField("対象年月/年度", max_length=10, help_text="YYYY-MM または YYYY")
    severity = models.CharField("深刻度", max_length=10, choices=AlertSeverity.choices)
    detail = models.JSONField("詳細", default=dict, blank=True)
    detected_at = models.DateTimeField("検知日時", auto_now_add=True)
    resolved_at = models.DateTimeField("解消日時", null=True, blank=True)

    class Meta:
        verbose_name = verbose_name_plural = "アラート"
        ordering = ["-detected_at"]
        indexes = [models.Index(fields=["alert_type", "target_period"])]

    def __str__(self) -> str:
        return f"{self.user} {self.get_alert_type_display()} {self.target_period}"
