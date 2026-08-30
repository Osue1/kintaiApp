from django.contrib import admin

from .models import Alert, OvertimeLimitPolicy


@admin.register(OvertimeLimitPolicy)
class OvertimeLimitPolicyAdmin(admin.ModelAdmin):
    list_display = ["name", "monthly_limit_minutes", "annual_limit_minutes", "special_clause_enabled", "is_default"]


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ["user", "alert_type", "target_period", "severity", "detected_at", "resolved_at"]
    list_filter = ["alert_type", "severity"]
    search_fields = ["user__name"]

    def has_add_permission(self, request) -> bool:
        return False
