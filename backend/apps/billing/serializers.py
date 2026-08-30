from rest_framework import serializers

from .models import Invoice, WithholdingStatement


class InvoiceSerializer(serializers.ModelSerializer):
    contractor_name = serializers.CharField(source="contractor.name", read_only=True)
    quantity_label = serializers.SerializerMethodField()
    confirm_deadline = serializers.SerializerMethodField()
    confirmed_at = serializers.SerializerMethodField()
    confirm_method = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            "id",
            "contractor_id",
            "contractor_name",
            "invoice_no",
            "period_start",
            "period_end",
            "quantity_label",
            "subtotal",
            "tax_amount",
            "withholding_amount",
            "payable_amount",
            "status",
            "issued_on",
            "confirm_deadline",
            "confirmed_at",
            "confirm_method",
        ]

    def get_confirm_deadline(self, obj) -> str | None:
        confirmation = getattr(obj, "confirmation", None)
        return confirmation.confirm_deadline.isoformat() if confirmation and confirmation.confirm_deadline else None

    def get_confirmed_at(self, obj) -> str | None:
        confirmation = getattr(obj, "confirmation", None)
        return confirmation.confirmed_at.isoformat() if confirmation and confirmation.confirmed_at else None

    def get_confirm_method(self, obj) -> str | None:
        confirmation = getattr(obj, "confirmation", None)
        return confirmation.confirm_method if confirmation else None

    def get_quantity_label(self, obj: Invoice) -> str:
        line = obj.lines.first()
        return line.description if line else ""


class GenerateInvoicesSerializer(serializers.Serializer):
    year_month = serializers.RegexField(r"^\d{4}-\d{2}$")


class WithholdingStatementSerializer(serializers.ModelSerializer):
    contractor_name = serializers.CharField(source="contractor.name", read_only=True)

    class Meta:
        model = WithholdingStatement
        fields = ["id", "contractor_id", "contractor_name", "year", "total_payment", "total_withholding"]


class AnnualStatementsSerializer(serializers.Serializer):
    year = serializers.IntegerField(min_value=2000, max_value=2100)
