from django.contrib import admin

from apps.common.admin import SubtitleAdminMixin

from .models import Contractor, ContractorClosing, ContractorRate, ContractorWorkRecord


class ContractorRateInline(admin.TabularInline):
    model = ContractorRate
    extra = 0


@admin.register(Contractor)
class ContractorAdmin(SubtitleAdminMixin, admin.ModelAdmin):
    changelist_subtitle = (
        "業務委託先（外注先）マスタ。ログインアカウントは持たない（社員ではないため）。"
        "「締め日」「支払月オフセット」「支払日」の組み合わせで請求書の対象期間と支払期日が"
        "決まる（例: 締め日31日・オフセット1・支払日10日 = 月末締め翌月10日払い）。"
        "単価は下の「外注単価履歴」で適用開始日つきに管理する（値上げ時も履歴が残る）。"
    )
    list_display = ["name", "tax_category", "closing_day", "payment_month_offset", "payment_day", "is_active"]
    list_filter = ["tax_category", "is_active"]
    search_fields = ["name"]
    inlines = [ContractorRateInline]


@admin.register(ContractorWorkRecord)
class ContractorWorkRecordAdmin(admin.ModelAdmin):
    list_display = ["contractor", "year_month", "hours", "days", "fixed_applied"]
    list_filter = ["year_month"]


@admin.register(ContractorClosing)
class ContractorClosingAdmin(admin.ModelAdmin):
    list_display = ["contractor", "period_start", "period_end", "payment_due_date", "status"]
    list_filter = ["status"]
