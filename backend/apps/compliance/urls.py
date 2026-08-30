from django.urls import path

from .views import AdminAlertsView, AdminApprovalsView, AdminAuditLogListView

urlpatterns = [
    path("approvals", AdminApprovalsView.as_view(), name="admin-approvals"),
    path("alerts", AdminAlertsView.as_view(), name="admin-alerts"),
    path("audit-logs", AdminAuditLogListView.as_view(), name="admin-audit-logs"),
]
