from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import AuditLog, Company, PasswordResetToken, Team, User


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ["name", "invoice_reg_no", "rounding_mode"]

    def has_add_permission(self, request) -> bool:
        # 会社設定は1行のみ
        return not Company.objects.exists()

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["name"]
    list_display = ["name", "email", "role", "team", "work_pattern", "leave_policy", "hire_date", "is_active"]
    list_filter = ["role", "team", "is_active"]
    search_fields = ["name", "email"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("基本情報", {"fields": ("name", "role", "team", "work_pattern", "leave_policy", "hire_date", "retired_at")}),
        ("権限", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "name", "role", "password1", "password2")}),
    )


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "actor", "action", "target_type", "target_id"]
    list_filter = ["action", "target_type"]
    search_fields = ["action", "target_type"]
    date_hierarchy = "created_at"

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    # token_hash は復元不能なハッシュ値のみで、そもそも一覧に出しても意味がないため列挙しない。
    list_display = ["user", "created_at", "expires_at", "used_at"]
    list_filter = ["used_at"]
    search_fields = ["user__email", "user__name"]
    date_hierarchy = "created_at"

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False
