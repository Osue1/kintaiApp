from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.common.models import TimeStampedModel


class TaxCategory(models.TextChoices):
    TAXABLE = "taxable", "課税事業者"
    EXEMPT = "exempt", "免税事業者"


class RateType(models.TextChoices):
    HOURLY = "hourly", "時給制"
    DAILY = "daily", "日給制"
    FIXED = "fixed", "固定額制"


class Contractor(TimeStampedModel):
    """外注先マスタ。ログイン主体を持たない（設計書 第4.2章）。"""

    name = models.CharField("名前・屋号", max_length=120)
    email = models.EmailField("メールアドレス", blank=True, help_text="請求書送信先")
    tax_category = models.CharField(
        "課税区分", max_length=10, choices=TaxCategory.choices, default=TaxCategory.TAXABLE
    )
    invoice_reg_no = models.CharField("インボイス登録番号", max_length=14, blank=True)
    withholding_target = models.BooleanField("源泉徴収対象", default=True, help_text="個人事業主は対象、法人は対象外")
    closing_day = models.PositiveSmallIntegerField(
        "締め日", default=31, validators=[MinValueValidator(1), MaxValueValidator(31)], help_text="31=月末"
    )
    payment_month_offset = models.PositiveSmallIntegerField(
        "支払月オフセット", default=1, validators=[MaxValueValidator(2)], help_text="0=当月 1=翌月 2=翌々月"
    )
    payment_day = models.PositiveSmallIntegerField(
        "支払日", default=10, validators=[MinValueValidator(1), MaxValueValidator(31)], help_text="31=月末"
    )
    bank_info = models.CharField("振込先", max_length=200, blank=True)
    is_active = models.BooleanField("有効", default=True)

    class Meta:
        verbose_name = verbose_name_plural = "外注先"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class ContractorRate(models.Model):
    """単価タイプと単価額を、適用開始日つきの履歴で保持する（設計書 第4.1章 ③）。"""

    contractor = models.ForeignKey(
        Contractor, verbose_name="外注先", on_delete=models.CASCADE, related_name="rates"
    )
    rate_type = models.CharField("単価タイプ", max_length=10, choices=RateType.choices)
    rate_amount = models.DecimalField("単価額", max_digits=10, decimal_places=0)
    effective_from = models.DateField("適用開始日")
    effective_to = models.DateField("適用終了日", null=True, blank=True, help_text="空欄は現在も有効")

    class Meta:
        verbose_name = verbose_name_plural = "外注単価履歴"
        ordering = ["-effective_from"]

    def __str__(self) -> str:
        return f"{self.contractor} {self.get_rate_type_display()} ¥{self.rate_amount}"


class ContractorWorkRecord(TimeStampedModel):
    """稼働実績。管理者が代行入力する（設計書 第9章）。"""

    contractor = models.ForeignKey(
        Contractor, verbose_name="外注先", on_delete=models.CASCADE, related_name="work_records"
    )
    year_month = models.CharField("対象年月", max_length=7, help_text="YYYY-MM")
    hours = models.DecimalField("稼働時間", max_digits=6, decimal_places=1, null=True, blank=True)
    days = models.DecimalField("稼働日数", max_digits=5, decimal_places=1, null=True, blank=True)
    fixed_applied = models.BooleanField("固定額を適用", default=False)
    note = models.CharField("備考", max_length=200, blank=True)
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="入力者", on_delete=models.SET_NULL, null=True, related_name="+"
    )

    class Meta:
        verbose_name = verbose_name_plural = "外注稼働実績"
        ordering = ["-year_month"]
        constraints = [
            models.UniqueConstraint(
                fields=["contractor", "year_month"], name="uniq_work_record_contractor_ym"
            )
        ]

    def __str__(self) -> str:
        return f"{self.contractor} {self.year_month}"


class ClosingStatus(models.TextChoices):
    OPEN = "open", "未締め"
    CLOSED = "closed", "締め済み"
    INVOICED = "invoiced", "請求書発行済み"


class ContractorClosing(models.Model):
    """締めサイクル。請求書生成時に対象期間・締め日・支払期日を記録する（設計書 第8.1章）。"""

    contractor = models.ForeignKey(
        Contractor, verbose_name="外注先", on_delete=models.CASCADE, related_name="closings"
    )
    period_start = models.DateField("対象期間開始")
    period_end = models.DateField("対象期間終了（締め日）")
    payment_due_date = models.DateField("支払期日")
    status = models.CharField("状態", max_length=10, choices=ClosingStatus.choices, default=ClosingStatus.OPEN)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)

    class Meta:
        verbose_name = verbose_name_plural = "外注締めサイクル"
        ordering = ["-period_end"]
        constraints = [
            models.UniqueConstraint(
                fields=["contractor", "period_end"], name="uniq_closing_contractor_period_end"
            )
        ]

    def __str__(self) -> str:
        return f"{self.contractor} 〜{self.period_end}"
