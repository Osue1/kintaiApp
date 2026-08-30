from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.common.admin import SubtitleAdminMixin

from .models import AuditLog, Company, PasswordResetToken, Team, User


@admin.register(Company)
class CompanyAdmin(SubtitleAdminMixin, admin.ModelAdmin):
    changelist_subtitle = (
        "自社の会社情報。請求書・支払調書のPDFに印字される。この画面には常に1行だけ存在する"
        "（追加・削除はできない設計）。「インボイス登録番号」は適格請求書発行事業者の登録番号"
        "（T+13桁）、「消費税の端数処理」は請求書の消費税額を計算する際の端数の扱い方。"
    )
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
class AuditLogAdmin(SubtitleAdminMixin, admin.ModelAdmin):
    changelist_subtitle = (
        "誰が・いつ・何を変更したかの操作履歴（承認・請求書取消・従業員情報の変更など）。"
        "改ざん防止のため、この画面からの追加・変更・削除はできない（閲覧専用）。"
        "同じ内容は「監査ログ」画面（管理者向けフロントエンド）からも確認できる。"
    )
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
class PasswordResetTokenAdmin(SubtitleAdminMixin, admin.ModelAdmin):
    changelist_subtitle = (
        "「パスワードをお忘れですか？」から発行されたリセット用トークンの記録（ハッシュ化済み、"
        "トークン自体の値はここから見えない）。発行から30分で失効し、使用済みかどうかは"
        "「used_at」列で分かる。トラブル調査用の記録で、通常は編集不要。"
    )
    # token_hash は復元不能なハッシュ値のみで、そもそも一覧に出しても意味がないため列挙しない。
    list_display = ["user", "created_at", "expires_at", "used_at"]
    list_filter = ["used_at"]
    search_fields = ["user__email", "user__name"]
    date_hierarchy = "created_at"

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False
