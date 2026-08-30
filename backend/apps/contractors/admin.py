from django.contrib import admin

from .models import Contractor, ContractorClosing, ContractorRate, ContractorWorkRecord


class ContractorRateInline(admin.TabularInline):
    model = ContractorRate
    extra = 0


@admin.register(Contractor)
class ContractorAdmin(admin.ModelAdmin):
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
