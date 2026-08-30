from django.conf import settings
from django.contrib import admin
from django.contrib.admin.sites import NotRegistered

from .models import IdempotencyKey


class SubtitleAdminMixin:
    """管理画面の一覧（changelist）タイトル直下に一言説明を出す。

    「この設定は何のためのものか」がモデル名だけでは伝わらない画面
    （マスタ・ポリシー系）向け。Django標準のsubtitleコンテキスト変数
    （4.0以降、テンプレート改造なしで使える）に差し込むだけなので、
    継承先で changelist_subtitle を書くだけで使える。
    """

    changelist_subtitle: str = ""

    class Media:
        # 説明文と「追加」ボタンが重なる問題の見た目調整。この一覧画面だけに
        # 読み込む（他の一覧画面のボタン位置に影響を与えないため）。
        css = {"all": ("common/css/admin_subtitle_fix.css",)}

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        if self.changelist_subtitle:
            extra_context.setdefault("subtitle", self.changelist_subtitle)
        return super().changelist_view(request, extra_context=extra_context)  # type: ignore[misc]


@admin.register(IdempotencyKey)
class IdempotencyKeyAdmin(SubtitleAdminMixin, admin.ModelAdmin):
    changelist_subtitle = (
        "二重送信防止の記録。打刻・請求書生成など「もう一度実行すると危険な操作」で、"
        "同じリクエストが2回届いても2重に処理しないための一時データです。"
        "手動で編集・削除する必要はありません（期限切れ分は自動で消えます）。"
    )
    list_display = ("endpoint", "key", "user", "response_status", "created_at")
    list_filter = ("endpoint",)
    search_fields = ("key",)


# ---- django-axes（ログイン失敗監視）の一覧に説明を追加する ----
#
# アプリ名・モデル名の日本語化は apps/common/axes_app_config.py で行っている。
# ここでは axes 標準の ModelAdmin（list_display 等）はそのまま活かしつつ、
# 「これは何のための一覧か」をchangelist画面に一言添える。
# AXES_ENABLE_ADMIN=False の環境では axes 側がそもそも登録しないため、
# unregister が失敗しても無視する。
try:
    from axes.admin import AccessAttemptAdmin, AccessFailureLogAdmin, AccessLogAdmin
    from axes.models import AccessAttempt, AccessFailureLog, AccessLog

    _failure_limit = getattr(settings, "AXES_FAILURE_LIMIT", 5)
    _cooloff_minutes = int(getattr(settings, "AXES_COOLOFF_TIME", 1) * 60)

    admin.site.unregister(AccessAttempt)
    admin.site.unregister(AccessLog)
    admin.site.unregister(AccessFailureLog)

    @admin.register(AccessAttempt)
    class LocalizedAccessAttemptAdmin(SubtitleAdminMixin, AccessAttemptAdmin):
        changelist_subtitle = (
            f"ログイン失敗の連続回数を数えている記録です。同じユーザー名で"
            f"{_failure_limit}回連続失敗すると{_cooloff_minutes}分間ロックされ、"
            "ログインに成功する（またはロックが解けて再挑戦がリセットされる）とこの行は消えます。"
            "手動で削除すればその場でロックを解除できます。"
        )

    @admin.register(AccessLog)
    class LocalizedAccessLogAdmin(SubtitleAdminMixin, AccessLogAdmin):
        changelist_subtitle = (
            "ログインに成功した記録の履歴です（いつ・どのIPアドレスから・いつログアウトしたか）。"
            "不正アクセスの調査以外で編集・削除する必要はありません。"
        )

    @admin.register(AccessFailureLog)
    class LocalizedAccessFailureLogAdmin(SubtitleAdminMixin, AccessFailureLogAdmin):
        changelist_subtitle = (
            "ログイン失敗の履歴です（上の「ログイン失敗（ロック判定中）」と違い、"
            "こちらは成功してもロックが解けても消えません）。"
            "「この失敗でロックされたか」列がONの行は、実際にアカウントがロックされる"
            "原因になった失敗です。"
        )
except (ImportError, NotRegistered):
    # axes未導入、またはAXES_ENABLE_ADMIN=False等でaxes側が最初から登録していない場合。
    pass
