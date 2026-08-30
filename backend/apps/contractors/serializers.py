from decimal import Decimal

from rest_framework import serializers

from .models import Contractor, ContractorWorkRecord


class ContractorCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    rate_type = serializers.ChoiceField(choices=["hourly", "daily", "fixed"])
    rate_amount = serializers.DecimalField(max_digits=10, decimal_places=0, min_value=Decimal("0"))
    closing_day = serializers.IntegerField(min_value=1, max_value=31)
    payment_month_offset = serializers.IntegerField(min_value=0, max_value=2)
    payment_day = serializers.IntegerField(min_value=1, max_value=31)


class ContractorSerializer(serializers.ModelSerializer):
    rate_type = serializers.SerializerMethodField()
    rate_amount = serializers.SerializerMethodField()

    class Meta:
        model = Contractor
        fields = [
            "id",
            "name",
            "email",
            "rate_type",
            "rate_amount",
            "closing_day",
            "payment_month_offset",
            "payment_day",
        ]

    def get_rate_type(self, obj: Contractor) -> str | None:
        rate = self._current_rate(obj)
        return rate.rate_type if rate else None

    def get_rate_amount(self, obj: Contractor):
        rate = self._current_rate(obj)
        return rate.rate_amount if rate else None

    def _current_rate(self, obj: Contractor):
        from datetime import date

        from apps.contractors.services.rates import RateHistoryRow, resolve_rate

        rows = tuple(
            RateHistoryRow(r.id, r.rate_type, r.rate_amount, r.effective_from, r.effective_to)
            for r in obj.rates.all()
        )
        return resolve_rate(rows, date.today())


class WorkRecordSerializer(serializers.ModelSerializer):
    contractor_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = ContractorWorkRecord
        fields = ["id", "contractor_id", "year_month", "hours", "days", "fixed_applied", "note"]


class WorkRecordUpsertSerializer(serializers.Serializer):
    contractor_id = serializers.IntegerField()
    year_month = serializers.RegexField(r"^\d{4}-\d{2}$")
    hours = serializers.DecimalField(max_digits=6, decimal_places=1, required=False, allow_null=True)
    days = serializers.DecimalField(max_digits=5, decimal_places=1, required=False, allow_null=True)
    fixed_applied = serializers.BooleanField(required=False, default=False)
    note = serializers.CharField(allow_blank=True, required=False, default="")
