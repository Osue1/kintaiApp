from django.contrib import admin

from apps.common.admin import SubtitleAdminMixin

from .models import (
    ExemptDeductionRate,
    Invoice,
    InvoiceConfirmation,
    InvoiceDelivery,
    InvoiceLine,
    TaxRate,
    WithholdingRule,
    WithholdingStatement,
)


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ["invoice_no", "contractor", "period_end", "subtotal", "payable_amount", "status"]
    list_filter = ["status"]
    search_fields = ["invoice_no", "contractor__name"]
    inlines = [InvoiceLineInline]


@admin.register(InvoiceDelivery)
class InvoiceDeliveryAdmin(admin.ModelAdmin):
    list_display = ["invoice", "recipient_email", "sent_at", "status"]

    def has_add_permission(self, request) -> bool:
        return False


@admin.register(InvoiceConfirmation)
class InvoiceConfirmationAdmin(admin.ModelAdmin):
    list_display = ["invoice", "notified_at", "confirm_deadline", "confirmed_at"]


@admin.register(WithholdingStatement)
class WithholdingStatementAdmin(admin.ModelAdmin):
    list_display = ["contractor", "year", "total_payment", "total_withholding"]

    def has_add_permission(self, request) -> bool:
        return False


class _LawMasterAdmin(SubtitleAdminMixin, admin.ModelAdmin):
    """法令マスタは編集させない（設計書 第4章）。閲覧のみ許可する。

    改正のたびにコード側でデータマイグレーションとして配布するため、この画面はあくまで
    「現在どの値が有効か」を確認するための閲覧専用画面（追加・変更・削除ボタンが無いのは
    バグではなく仕様）。
    """

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(TaxRate)
class TaxRateAdmin(_LawMasterAdmin):
    changelist_subtitle = (
        "消費税率マスタ（閲覧専用）。請求書の税額計算に使う税率とその適用期間の履歴。"
        "法改正はアプリの更新（データマイグレーション）で反映するため、この画面からは編集できない。"
    )
    list_display = ["category", "rate_percent", "effective_from", "effective_to"]


@admin.register(ExemptDeductionRate)
class ExemptDeductionRateAdmin(_LawMasterAdmin):
    changelist_subtitle = (
        "免税事業者（インボイス未登録の外注先）からの仕入に対する、消費税の経過措置控除率"
        "マスタ（閲覧専用）。2023年10月のインボイス制度開始からの経過措置で、"
        "期間が進むごとに控除できる割合が下がっていく（80%→50%→0%）。"
    )
    list_display = ["deduction_percent", "effective_from", "effective_to"]


@admin.register(WithholdingRule)
class WithholdingRuleAdmin(_LawMasterAdmin):
    changelist_subtitle = (
        "源泉徴収税率マスタ（閲覧専用）。個人事業主への支払額から天引きする源泉所得税の"
        "税率と、税率が変わる金額の境目（閾値）。「閾値以下」は原則10.21%、"
        "「閾値超過分」はその超えた金額に対して20.42%という2段階の計算になる。"
    )
    list_display = ["threshold_amount", "rate_below_percent", "rate_above_percent", "effective_from", "effective_to"]
