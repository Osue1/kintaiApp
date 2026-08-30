from django.contrib import admin

from .models import (
    LeaveAbsencePeriod,
    LeaveConsumption,
    LeaveRequest,
    LeaveType,
    PaidLeaveGrant,
    PaidLeaveGrantRule,
    PaidLeavePolicy,
)


class PaidLeaveGrantRuleInline(admin.TabularInline):
    model = PaidLeaveGrantRule
    extra = 1


@admin.register(PaidLeavePolicy)
class PaidLeavePolicyAdmin(admin.ModelAdmin):
    list_display = ["name", "grant_method", "carryover_limit_days", "expiry_years", "required_attendance_rate", "is_default"]
    inlines = [PaidLeaveGrantRuleInline]


@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ["name", "is_paid", "supports_half_day", "requires_period", "counts_toward_mandatory_five", "is_active"]
    list_filter = ["is_paid", "is_active"]


@admin.register(PaidLeaveGrant)
class PaidLeaveGrantAdmin(admin.ModelAdmin):
    list_display = ["user", "policy", "granted_on", "days", "expires_on"]
    list_filter = ["policy"]
    search_fields = ["user__name", "user__email"]
    date_hierarchy = "granted_on"


@admin.register(LeaveConsumption)
class LeaveConsumptionAdmin(admin.ModelAdmin):
    list_display = ["grant", "leave_request", "days", "created_at"]

    def has_add_permission(self, request) -> bool:
        return False


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ["user", "leave_type", "start_date", "end_date", "unit", "days", "status"]
    list_filter = ["status", "leave_type"]
    search_fields = ["user__name"]
    date_hierarchy = "start_date"


@admin.register(LeaveAbsencePeriod)
class LeaveAbsencePeriodAdmin(admin.ModelAdmin):
    list_display = ["user", "leave_type", "start_date", "end_date"]
    list_filter = ["leave_type"]
