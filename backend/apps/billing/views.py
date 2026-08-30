from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.audit import record_audit
from apps.common.idempotency import with_idempotency
from apps.common.permissions import IsAdminRole
from apps.notifications.services import notify

from .models import Invoice, InvoiceStatus, WithholdingStatement
from .serializers import (
    AnnualStatementsSerializer,
    GenerateInvoicesSerializer,
    InvoiceSerializer,
    WithholdingStatementSerializer,
)
from .services.confirmation import confirm_manually, notify_for_confirmation
from .services.generate import generate_invoices_for_month
from .services.mail import send_invoice_email
from .services.pdf import read_pdf, render_invoice_pdf, render_withholding_statement_pdf
from .services.statements import generate_annual_statements
from .services.void import InvoiceVoidError, void_invoice


class InvoiceListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    @extend_schema(summary="請求書の一覧")
    def get(self, request: Request) -> Response:
        year_month = request.query_params.get("year_month")
        qs = Invoice.objects.select_related("contractor", "confirmation").prefetch_related("lines")
        if year_month:
            year, month = (int(p) for p in year_month.split("-"))
            qs = qs.filter(period_end__year=year, period_end__month=month)
        return Response(InvoiceSerializer(qs, many=True).data)


class GenerateInvoicesView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    @extend_schema(request=GenerateInvoicesSerializer, summary="締め日到来分の請求書を一括生成")
    def post(self, request: Request) -> Response:
        def handle() -> Response:
            serializer = GenerateInvoicesSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            result = generate_invoices_for_month(serializer.validated_data["year_month"], created_by=request.user)
            record_audit(
                request, "invoice_generate", "Invoice",
                after={"year_month": serializer.validated_data["year_month"], "created_count": len(result.created)},
            )
            return Response(
                {
                    "created": InvoiceSerializer(result.created, many=True).data,
                    "created_count": len(result.created),
                    "skipped_no_record_count": len(result.skipped_no_record),
                    "already_exists_count": len(result.already_exists),
                }
            )

        return with_idempotency(request, "invoices-generate", handle)


class InvoiceSendView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    @extend_schema(summary="請求書PDFを送信")
    def post(self, request: Request, pk: int) -> Response:
        invoice = get_object_or_404(Invoice, pk=pk)
        if not invoice.contractor.email:
            return Response(
                {
                    "code": "missing_email",
                    "message": "外注先にメールアドレスが登録されていません。",
                    "field_errors": {},
                },
                status=400,
            )
        pdf_key = render_invoice_pdf(invoice)
        send_invoice_email(invoice, invoice.contractor.email, pdf_key)
        invoice.status = InvoiceStatus.SENT
        invoice.save(update_fields=["status"])
        confirmation = notify_for_confirmation(invoice)
        notify(
            request.user,
            "info",
            "請求書を送信しました",
            f"{invoice.contractor.name} 宛に {invoice.invoice_no} を送信しました。"
            f"確認期限は {confirmation.confirm_deadline} です。",
        )
        record_audit(
            request, "invoice_send", "Invoice", invoice.id,
            after={"invoice_no": invoice.invoice_no, "sent_to": invoice.contractor.email},
        )
        return Response(InvoiceSerializer(invoice).data)


class InvoiceConfirmView(APIView):
    """仕入明細書としての内容確認を、外注先からの連絡等を受けて管理者が手動で記録する（第8.5章）。
    期限を過ぎても未確認のままの分は confirm_invoices バッチが自動で「みなし確認」にする。"""

    permission_classes = [IsAuthenticated, IsAdminRole]

    @extend_schema(summary="仕入明細書の確認を手動で記録")
    def post(self, request: Request, pk: int) -> Response:
        invoice = get_object_or_404(Invoice, pk=pk)
        confirmation = getattr(invoice, "confirmation", None)
        if confirmation is None:
            return Response(
                {"code": "not_notified", "message": "この請求書はまだ送付（通知）されていません。", "field_errors": {}},
                status=400,
            )
        if confirmation.confirmed_at is not None:
            return Response(
                {"code": "already_confirmed", "message": "この請求書は既に確認済みです。", "field_errors": {}},
                status=400,
            )
        confirm_manually(confirmation)
        record_audit(request, "invoice_confirm", "Invoice", invoice.id, after={"confirm_method": "manual"})
        return Response(InvoiceSerializer(invoice).data)


class InvoiceVoidView(APIView):
    """請求書の取消（赤伝）。取消後は generate_invoices_for_month が対象月・外注先を
    「未生成」とみなすため、内容を修正して再度一括生成を実行すれば再発行できる（第8.6章）。"""

    permission_classes = [IsAuthenticated, IsAdminRole]

    @extend_schema(summary="請求書を取消（赤伝を発行）")
    def post(self, request: Request, pk: int) -> Response:
        invoice = get_object_or_404(Invoice, pk=pk)
        try:
            reversal = void_invoice(invoice, actor=request.user)
        except InvoiceVoidError as exc:
            return Response({"code": "invalid_state", "message": str(exc), "field_errors": {}}, status=400)
        notify(
            request.user,
            "info",
            "請求書を取消しました",
            f"{invoice.invoice_no} を取消し、赤伝 {reversal.invoice_no} を発行しました。",
        )
        record_audit(
            request, "invoice_void", "Invoice", invoice.id,
            after={"reversal_invoice_no": reversal.invoice_no, "reversal_invoice_id": reversal.id},
        )
        return Response(InvoiceSerializer(reversal).data, status=201)


class InvoicePdfView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    @extend_schema(summary="請求書PDFのダウンロード")
    def get(self, request: Request, pk: int) -> HttpResponse:
        invoice = get_object_or_404(Invoice, pk=pk)
        pdf_bytes = read_pdf(invoice.pdf_key)
        if pdf_bytes is None:
            # まだ生成されていない、またはストレージ側で失われている場合はその場で作り直す
            # （pdf_key はストレージ上のキーであり、ローカルファイルシステムのパスとは
            # 限らないため、ここも default_storage 経由の read_pdf() だけを見る）。
            render_invoice_pdf(invoice)
            invoice.refresh_from_db(fields=["pdf_key"])
            pdf_bytes = read_pdf(invoice.pdf_key)
        if pdf_bytes is None:
            raise Http404
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{invoice.invoice_no}.pdf"'
        return response


class AnnualStatementsView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    @extend_schema(summary="支払調書の一覧")
    def get(self, request: Request) -> Response:
        year = request.query_params.get("year")
        qs = WithholdingStatement.objects.select_related("contractor")
        if year:
            qs = qs.filter(year=int(year))
        return Response(WithholdingStatementSerializer(qs, many=True).data)

    @extend_schema(request=AnnualStatementsSerializer, summary="支払調書を年間一括出力")
    def post(self, request: Request) -> Response:
        serializer = AnnualStatementsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        statements = generate_annual_statements(serializer.validated_data["year"])
        record_audit(
            request, "withholding_statements_issue", "WithholdingStatement",
            after={"year": serializer.validated_data["year"], "count": len(statements)},
        )
        return Response(WithholdingStatementSerializer(statements, many=True).data)


class WithholdingStatementPdfView(APIView):
    """支払調書PDFのダウンロード。

    render_withholding_statement_pdf() はPDFを生成する関数として以前から存在していたが、
    それを呼び出すAPI（および画面側のダウンロード導線）が一つも無く、支払調書を「出力」
    しても実際のPDF文書を誰も取得できないという欠落があった（支払調書は所得税法上、
    支払先へ交付が求められる文書であるため実害がある）。InvoicePdfView と同じ
    「pdf_key が指すストレージ実体が無ければその場で再生成する」設計に揃えている。
    """

    permission_classes = [IsAuthenticated, IsAdminRole]

    @extend_schema(summary="支払調書PDFのダウンロード")
    def get(self, request: Request, pk: int) -> HttpResponse:
        statement = get_object_or_404(WithholdingStatement, pk=pk)
        pdf_bytes = read_pdf(statement.pdf_key)
        if pdf_bytes is None:
            render_withholding_statement_pdf(statement)
            statement.refresh_from_db(fields=["pdf_key"])
            pdf_bytes = read_pdf(statement.pdf_key)
        if pdf_bytes is None:
            raise Http404
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="withholding_statement_{statement.contractor_id}_{statement.year}.pdf"'
        )
        return response
