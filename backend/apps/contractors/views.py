from datetime import date

from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.audit import record_audit
from apps.common.permissions import IsAdminRole

from .models import Contractor, ContractorRate, ContractorWorkRecord
from .serializers import (
    ContractorCreateSerializer,
    ContractorSerializer,
    WorkRecordSerializer,
    WorkRecordUpsertSerializer,
)


class ContractorListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    @extend_schema(summary="外注マスタの一覧")
    def get(self, request: Request) -> Response:
        qs = Contractor.objects.filter(is_active=True).prefetch_related("rates")
        return Response(ContractorSerializer(qs, many=True).data)

    @extend_schema(request=ContractorCreateSerializer, summary="外注先を登録")
    @transaction.atomic
    def post(self, request: Request) -> Response:
        serializer = ContractorCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        contractor = Contractor.objects.create(
            name=data["name"],
            email=data.get("email", ""),
            closing_day=data["closing_day"],
            payment_month_offset=data["payment_month_offset"],
            payment_day=data["payment_day"],
        )
        ContractorRate.objects.create(
            contractor=contractor,
            rate_type=data["rate_type"],
            rate_amount=data["rate_amount"],
            effective_from=date.today(),
        )
        contractor.refresh_from_db()
        record_audit(
            request, "contractor_create", "Contractor", contractor.id,
            after={"name": contractor.name, "rate_type": data["rate_type"], "rate_amount": str(data["rate_amount"])},
        )
        return Response(ContractorSerializer(contractor).data, status=201)


class WorkRecordListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    @extend_schema(summary="外注稼働実績の一覧")
    def get(self, request: Request) -> Response:
        year_month = request.query_params.get("year_month")
        qs = ContractorWorkRecord.objects.all()
        if year_month:
            qs = qs.filter(year_month=year_month)
        return Response(WorkRecordSerializer(qs, many=True).data)

    @extend_schema(request=WorkRecordUpsertSerializer, summary="外注稼働実績を保存（代行入力）")
    def post(self, request: Request) -> Response:
        serializer = WorkRecordUpsertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        existing = ContractorWorkRecord.objects.filter(
            contractor_id=data["contractor_id"], year_month=data["year_month"]
        ).first()
        before = (
            {"hours": str(existing.hours), "days": str(existing.days), "fixed_applied": existing.fixed_applied}
            if existing
            else None
        )
        record, _ = ContractorWorkRecord.objects.update_or_create(
            contractor_id=data["contractor_id"],
            year_month=data["year_month"],
            defaults={
                "hours": data.get("hours"),
                "days": data.get("days"),
                "fixed_applied": data.get("fixed_applied", False),
                "note": data.get("note", ""),
                "entered_by": request.user,
            },
        )
        record_audit(
            request, "contractor_work_record_save", "ContractorWorkRecord", record.id,
            before=before,
            after={"hours": str(record.hours), "days": str(record.days), "fixed_applied": record.fixed_applied},
        )
        return Response(WorkRecordSerializer(record).data, status=200)
