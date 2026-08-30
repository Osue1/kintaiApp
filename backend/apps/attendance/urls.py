from django.urls import path

from .views import (
    AdminCorrectionApproveView,
    AdminCorrectionRejectView,
    AdminMonthlyApproveView,
    AdminMonthlyRejectView,
    AdminMonthlyReopenView,
    CorrectionRequestListCreateView,
    DashboardView,
    MonthlyDetailView,
    MonthlySubmitView,
    PunchView,
    TeamStatusView,
)

urlpatterns = [
    path("dashboard", DashboardView.as_view(), name="attendance-dashboard"),
    path("monthly", MonthlyDetailView.as_view(), name="attendance-monthly"),
    path("monthly/submit", MonthlySubmitView.as_view(), name="attendance-monthly-submit"),
    path("status", TeamStatusView.as_view(), name="attendance-status"),
    path("punch", PunchView.as_view(), name="attendance-punch"),
    path("corrections", CorrectionRequestListCreateView.as_view(), name="attendance-corrections"),
    path(
        "admin/corrections/<int:pk>/approve",
        AdminCorrectionApproveView.as_view(),
        name="attendance-admin-correction-approve",
    ),
    path(
        "admin/corrections/<int:pk>/reject",
        AdminCorrectionRejectView.as_view(),
        name="attendance-admin-correction-reject",
    ),
    path(
        "admin/monthly/<int:pk>/approve",
        AdminMonthlyApproveView.as_view(),
        name="attendance-admin-monthly-approve",
    ),
    path(
        "admin/monthly/<int:pk>/reject",
        AdminMonthlyRejectView.as_view(),
        name="attendance-admin-monthly-reject",
    ),
    path(
        "admin/monthly/<int:pk>/reopen",
        AdminMonthlyReopenView.as_view(),
        name="attendance-admin-monthly-reopen",
    ),
]
