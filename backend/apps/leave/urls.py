from django.urls import path

from .views import (
    AdminLeaveApproveView,
    AdminLeaveRejectView,
    LeaveBalanceView,
    LeaveLedgerPdfView,
    LeaveLedgerView,
    LeaveRequestListCreateView,
    LeaveTypesView,
)

urlpatterns = [
    path("types", LeaveTypesView.as_view(), name="leave-types"),
    path("balance", LeaveBalanceView.as_view(), name="leave-balance"),
    path("requests", LeaveRequestListCreateView.as_view(), name="leave-requests"),
    path("admin/requests/<int:pk>/approve", AdminLeaveApproveView.as_view(), name="leave-admin-approve"),
    path("admin/requests/<int:pk>/reject", AdminLeaveRejectView.as_view(), name="leave-admin-reject"),
    path("admin/ledger", LeaveLedgerView.as_view(), name="leave-admin-ledger"),
    path("admin/ledger/pdf", LeaveLedgerPdfView.as_view(), name="leave-admin-ledger-pdf"),
]
