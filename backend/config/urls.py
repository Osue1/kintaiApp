from django.contrib import admin
from django.urls import include, path, re_path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.common.views import health, spa_index

urlpatterns = [
    # 集約監視から叩く。アプリのバージョンと最終マイグレーション名を返す（追補 第7.3章）
    path("healthz", health, name="health"),
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/attendance/", include("apps.attendance.urls")),
    path("api/v1/leave/", include("apps.leave.urls")),
    path("api/v1/notifications/", include("apps.notifications.urls")),
    path("api/v1/admin/", include("apps.compliance.urls")),
    path("api/v1/admin/employees/", include("apps.accounts.admin_urls")),
    path("api/v1/admin/contractors/", include("apps.contractors.urls")),
    path("api/v1/admin/invoices/", include("apps.billing.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    # フロントエンド（Vue SPA、history モード）のcatch-all。上記のどれにも
    # マッチしなかったパスは全てここに落として index.html を返す。必ず
    # urlpatterns の最後に置くこと（先に置くと他の全ルートを覆い隠してしまう）。
    re_path(r"^(?!api/|admin/|static/|media/|healthz$).*$", spa_index, name="spa-index"),
]
