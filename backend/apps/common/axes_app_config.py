"""django-axes（ログイン失敗監視）の管理画面表示を日本語化する。

axes はサードパーティ製ライブラリで、アプリ名・モデル名の verbose_name が
英語の生文字列のまま定義されている（gettext_lazy でラップされていないため、
LANGUAGE_CODE="ja" にしていても自動翻訳の対象にならない）。ライブラリ本体は
変更したくないので、ready() の中でメタ情報だけを上書きしてラベルを差し替える。

これにより管理画面の左メニューが英語のまま残ってしまう問題
（"Axes" / "Access attempts" / "Access failures" / "Access logs" が
何の設定か分からない）に対応する。実際の一覧・注釈表示のカスタムは
apps/common/admin.py の AccessAttemptAdmin 等で行う。
"""
from axes.apps import AppConfig as AxesAppConfig


class LocalizedAxesConfig(AxesAppConfig):
    """config/settings/base.py の INSTALLED_APPS から "axes" の代わりに指定する。"""

    verbose_name = "ログイン試行監視（django-axes）"

    def ready(self) -> None:
        super().ready()
        self._localize_models()

    def _localize_models(self) -> None:
        # settings.py で "axes" ではなくこのクラスを INSTALLED_APPS に登録して
        # いる限り、モデル自体は同じ axes.models のものを使う（テーブルは
        # 変わらない）。表示ラベルだけをここで上書きする。
        from axes.models import AccessAttempt, AccessFailureLog, AccessLog

        AccessAttempt._meta.verbose_name = "ログイン失敗（ロック判定中）"
        AccessAttempt._meta.verbose_name_plural = "ログイン失敗（ロック判定中）"

        AccessLog._meta.verbose_name = "ログイン履歴"
        AccessLog._meta.verbose_name_plural = "ログイン履歴（成功・ログアウト）"

        AccessFailureLog._meta.verbose_name = "ログイン失敗履歴"
        AccessFailureLog._meta.verbose_name_plural = "ログイン失敗履歴（消えない記録）"

        field_labels = {
            "ip_address": "IPアドレス",
            "user_agent": "ブラウザ情報（User-Agent）",
            "http_accept": "Acceptヘッダ",
            "path_info": "アクセス先パス",
            "attempt_time": "試行日時",
            "get_data": "GETパラメータ",
            "post_data": "POSTパラメータ（パスワードは***で伏せられる）",
            "failures_since_start": "連続失敗回数",
            "logout_time": "ログアウト日時",
            "locked_out": "この失敗でロックされたか",
        }
        for model in (AccessAttempt, AccessLog, AccessFailureLog):
            for field_name, label in field_labels.items():
                try:
                    model._meta.get_field(field_name).verbose_name = label
                except Exception:  # noqa: BLE001 - フィールドが無いモデルもあるため無視
                    pass
