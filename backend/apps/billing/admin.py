from django.contrib import admin

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


class _LawMasterAdmin(admin.ModelAdmin):
    """法令マスタは編集させない（設計書 第4章）。閲覧のみ許可する。"""

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(TaxRate)
class TaxRateAdmin(_LawMasterAdmin):
    list_display = ["category", "rate_percent", "effective_from", "effective_to"]


@admin.register(ExemptDeductionRate)
class ExemptDeductionRateAdmin(_LawMasterAdmin):
    list_display = ["deduction_percent", "effective_from", "effective_to"]


@admin.register(WithholdingRule)
class WithholdingRuleAdmin(_LawMasterAdmin):
    list_display = ["threshold_amount", "rate_below_percent", "rate_above_percent", "effective_from", "effective_to"]
