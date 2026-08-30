from django.contrib import admin

from apps.common.admin import SubtitleAdminMixin

from .models import Alert, OvertimeLimitPolicy


@admin.register(OvertimeLimitPolicy)
class OvertimeLimitPolicyAdmin(SubtitleAdminMixin, admin.ModelAdmin):
    changelist_subtitle = (
        "時間外労働・休日労働に関する協定（いわゆる「36（サブロク）協定」）で届け出た上限値。"
        "残業がこの値に近づく・超えるとアラート画面に表示される。時間はすべて「分」単位で"
        "入力する（例: 45時間 = 2700分）。「特別条項」は臨時的な特別の事情がある場合に"
        "上限を一時的に引き上げる協定条項（年6回まで等の制限あり）。"
    )
    list_display = ["name", "monthly_limit_minutes", "annual_limit_minutes", "special_clause_enabled", "is_default"]


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ["user", "alert_type", "target_period", "severity", "detected_at", "resolved_at"]
    list_filter = ["alert_type", "severity"]
    search_fields = ["user__name"]

    def has_add_permission(self, request) -> bool:
        return False
