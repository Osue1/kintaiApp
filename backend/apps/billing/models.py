from django.db import models

from apps.common.models import TimeStampedModel


class TaxCategory(models.TextChoices):
    STANDARD = "standard", "標準税率(10%)"
    REDUCED = "reduced", "軽減税率(8%)"
    EXEMPT = "exempt", "対象外"


class TaxRate(models.Model):
    """消費税率と適用期間（設計書 第4章 tax_rate）。法令マスタのため管理画面からは編集させない。"""

    category = models.CharField("税率区分", max_length=10, choices=TaxCategory.choices)
    rate_percent = models.DecimalField("税率(%)", max_digits=5, decimal_places=2)
    effective_from = models.DateField("適用開始日")
    effective_to = models.DateField("適用終了日", null=True, blank=True)

    class Meta:
        verbose_name = verbose_name_plural = "消費税率マスタ"
        ordering = ["-effective_from"]

    def __str__(self) -> str:
        return f"{self.get_category_display()} {self.rate_percent}%"


class ExemptDeductionRate(models.Model):
    """免税事業者からの仕入に対する経過措置控除率（設計書 第8.4章）。

    〜2026-09-30: 80% / 2026-10-01〜2029-09-30: 50% / 以降: 0%
    """

    deduction_percent = models.DecimalField("控除割合(%)", max_digits=5, decimal_places=2)
    effective_from = models.DateField("適用開始日")
    effective_to = models.DateField("適用終了日", null=True, blank=True)

    class Meta:
        verbose_name = verbose_name_plural = "免税事業者 経過措置控除率マスタ"
        ordering = ["-effective_from"]

    def __str__(self) -> str:
        return f"{self.deduction_percent}% ({self.effective_from}〜{self.effective_to or ''})"


class WithholdingRule(models.Model):
    """源泉徴収の税率と閾値（設計書 第4章 withholding_rule・第8.3章）。"""

    threshold_amount = models.DecimalField("閾値", max_digits=12, decimal_places=0, default=1_000_000)
    rate_below_percent = models.DecimalField("閾値以下の税率(%)", max_digits=5, decimal_places=2, default=10.21)
    rate_above_percent = models.DecimalField("閾値超過分の税率(%)", max_digits=5, decimal_places=2, default=20.42)
    effective_from = models.DateField("適用開始日")
    effective_to = models.DateField("適用終了日", null=True, blank=True)

    class Meta:
        verbose_name = verbose_name_plural = "源泉徴収税率マスタ"
        ordering = ["-effective_from"]

    def __str__(self) -> str:
        return f"源泉徴収 {self.rate_below_percent}%/{self.rate_above_percent}%"


class InvoiceStatus(models.TextChoices):
    DRAFT = "draft", "下書き"
    ISSUED = "issued", "発行確定"
    SENT = "sent", "送信済み"
    VOID = "void", "取消（赤伝）"


class Invoice(TimeStampedModel):
    """外注先への請求書（実体は仕入明細書）。発行確定後は内容変更不可（設計書 第8.6章）。"""

    contractor = models.ForeignKey(
        "contractors.Contractor", verbose_name="外注先", on_delete=models.PROTECT, related_name="invoices"
    )
    invoice_no = models.CharField("請求書番号", max_length=30, unique=True)
    issued_on = models.DateField("発行日")
    period_start = models.DateField("対象期間開始")
    period_end = models.DateField("対象期間終了")
    tax_category = models.CharField("税率区分", max_length=10, choices=TaxCategory.choices)
    subtotal = models.DecimalField("小計（税抜）", max_digits=12, decimal_places=0)
    tax_amount = models.DecimalField("消費税額", max_digits=12, decimal_places=0)
    withholding_amount = models.DecimalField("源泉徴収税額", max_digits=12, decimal_places=0, default=0)
    payable_amount = models.DecimalField("差引支払額", max_digits=12, decimal_places=0)
    exempt_deduction_percent = models.DecimalField(
        "免税事業者控除率(%)", max_digits=5, decimal_places=2, null=True, blank=True
    )
    status = models.CharField("状態", max_length=10, choices=InvoiceStatus.choices, default=InvoiceStatus.DRAFT)
    pdf_key = models.CharField("PDFファイルキー", max_length=255, blank=True)
    void_of = models.ForeignKey(
        "self", verbose_name="取消元", on_delete=models.SET_NULL, null=True, blank=True, related_name="voided_by"
    )
    created_by = models.ForeignKey(
        "accounts.User", verbose_name="作成者", on_delete=models.SET_NULL, null=True, related_name="+"
    )

    class Meta:
        verbose_name = verbose_name_plural = "請求書"
        ordering = ["-issued_on", "-id"]
        constraints = [
            # 同一外注先・同一対象期間について「有効な（取消済みでない）」請求書は常に1件まで
            # （設計書 第8.6章）。DBの部分一意インデックスとして強制することで、
            # 管理画面の「一括生成」ボタン連打や2人の管理者による同時実行といった競合状態でも
            # 二重発行（二重請求）を確実に防ぐ。アプリ層の「存在チェック→作成」だけでは
            # チェックと作成の間に別トランザクションが割り込む余地があり、防ぎきれないため、
            # 最終防衛線としてDB制約を必ず併設する（services/generate.py 側の運用は
            # apps/billing/services/generate.py の docstring を参照）。
            models.UniqueConstraint(
                fields=["contractor", "period_end"],
                condition=~models.Q(status="void"),
                name="uniq_active_invoice_per_contractor_period",
            )
        ]

    def __str__(self) -> str:
        return self.invoice_no


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, verbose_name="請求書", on_delete=models.CASCADE, related_name="lines")
    description = models.CharField("摘要", max_length=200)
    quantity = models.DecimalField("数量", max_digits=8, decimal_places=1, default=1)
    unit_price = models.DecimalField("単価", max_digits=12, decimal_places=0)
    amount = models.DecimalField("金額", max_digits=12, decimal_places=0)
    tax_category = models.CharField("税率区分", max_length=10, choices=TaxCategory.choices)
    withholding_applicable = models.BooleanField("源泉徴収対象", default=True)

    class Meta:
        verbose_name = verbose_name_plural = "請求書明細"

    def __str__(self) -> str:
        return f"{self.invoice} {self.description}"


class InvoiceConfirmation(models.Model):
    """仕入明細書としての相手方確認記録（設計書 第8.5章）。"""

    invoice = models.OneToOneField(
        Invoice, verbose_name="請求書", on_delete=models.CASCADE, related_name="confirmation"
    )
    notified_at = models.DateTimeField("通知日時", null=True, blank=True)
    confirm_deadline = models.DateField("確認期限")
    confirm_method = models.CharField(
        "確認方法", max_length=30, default="deemed_after_deadline", help_text="期限経過で確認済とみなす"
    )
    confirmed_at = models.DateTimeField("確認日時", null=True, blank=True)

    class Meta:
        verbose_name = verbose_name_plural = "仕入明細書確認記録"

    def __str__(self) -> str:
        return f"{self.invoice} 確認記録"


class DeliveryStatus(models.TextChoices):
    SENT = "sent", "送信済み"
    BOUNCED = "bounced", "バウンス"
    COMPLAINED = "complained", "苦情"
    FAILED = "failed", "送信失敗"


class InvoiceDelivery(models.Model):
    """送信ログ。設計はSES送信を想定するが、ローカル/小規模運用では標準SMTPでも動く（設計書 第2.5章）。"""

    invoice = models.ForeignKey(
        Invoice, verbose_name="請求書", on_delete=models.CASCADE, related_name="deliveries"
    )
    recipient_email = models.EmailField("宛先")
    sent_at = models.DateTimeField("送信日時", auto_now_add=True)
    status = models.CharField("状態", max_length=10, choices=DeliveryStatus.choices, default=DeliveryStatus.SENT)
    message_id = models.CharField("メッセージID", max_length=120, blank=True)

    class Meta:
        verbose_name = verbose_name_plural = "請求書送信ログ"
        ordering = ["-sent_at"]

    def __str__(self) -> str:
        return f"{self.invoice} → {self.recipient_email}"


class WithholdingStatement(models.Model):
    """支払調書。暦年ベースで年間一括出力する（設計書 第8.7章）。"""

    contractor = models.ForeignKey(
        "contractors.Contractor", verbose_name="外注先", on_delete=models.PROTECT, related_name="withholding_statements"
    )
    year = models.PositiveIntegerField("対象年")
    total_payment = models.DecimalField("支払金額合計", max_digits=12, decimal_places=0)
    total_withholding = models.DecimalField("源泉徴収税額合計", max_digits=12, decimal_places=0)
    pdf_key = models.CharField("PDFファイルキー", max_length=255, blank=True)
    generated_at = models.DateTimeField("生成日時", auto_now_add=True)

    class Meta:
        verbose_name = verbose_name_plural = "支払調書"
        ordering = ["-year", "contractor__name"]
        constraints = [
            models.UniqueConstraint(fields=["contractor", "year"], name="uniq_withholding_statement_contractor_year")
        ]

    def __str__(self) -> str:
        return f"{self.contractor} {self.year}年"
