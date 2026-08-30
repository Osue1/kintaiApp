from django.contrib import admin

from apps.common.admin import SubtitleAdminMixin

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
class PaidLeavePolicyAdmin(SubtitleAdminMixin, admin.ModelAdmin):
    changelist_subtitle = (
        "有給休暇の付与・繰越・失効ルール。従業員ごとに1つ割り当てる（従業員管理画面から割当）。"
        "「付与に必要な出勤率」は0.800のように「割合」で入力する（0.8 = 80%、法定は8割以上）。"
        "「繰越上限日数」は空欄で無制限。下の「有給付与テーブル」で勤続月数ごとの付与日数を設定する。"
    )
    list_display = ["name", "grant_method", "carryover_limit_days", "expiry_years", "required_attendance_rate", "is_default"]
    inlines = [PaidLeaveGrantRuleInline]


@admin.register(LeaveType)
class LeaveTypeAdmin(SubtitleAdminMixin, admin.ModelAdmin):
    changelist_subtitle = (
        "休暇の種類マスタ（年次有給休暇・慶弔休暇・産休等）。「年5日取得義務の対象」は"
        "年次有給休暇にだけONにする（この種類の休暇取得だけが年5日取得義務のカウント対象になる）。"
        "「期間管理」は産休・育休のように開始日〜終了日を別途記録したい休暇のみON。"
    )
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
