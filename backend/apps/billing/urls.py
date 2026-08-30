from django.urls import path

from .views import (
    AnnualStatementsView,
    GenerateInvoicesView,
    InvoiceConfirmView,
    InvoiceListView,
    InvoicePdfView,
    InvoiceSendView,
    InvoiceVoidView,
    WithholdingStatementPdfView,
)

urlpatterns = [
    path("", InvoiceListView.as_view(), name="invoices-list"),
    path("generate", GenerateInvoicesView.as_view(), name="invoices-generate"),
    path("<int:pk>/send", InvoiceSendView.as_view(), name="invoices-send"),
    path("<int:pk>/void", InvoiceVoidView.as_view(), name="invoices-void"),
    path("<int:pk>/confirm", InvoiceConfirmView.as_view(), name="invoices-confirm"),
    path("<int:pk>/pdf", InvoicePdfView.as_view(), name="invoices-pdf"),
    path("withholding-statements", AnnualStatementsView.as_view(), name="withholding-statements"),
    path(
        "withholding-statements/<int:pk>/pdf",
        WithholdingStatementPdfView.as_view(),
        name="withholding-statements-pdf",
    ),
]
