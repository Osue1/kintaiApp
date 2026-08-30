from rest_framework import serializers

from .models import LeaveRequest, LeaveType


class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = ["id", "name", "is_paid", "supports_half_day", "requires_reason"]


class LeaveRequestSerializer(serializers.ModelSerializer):
    type_id = serializers.IntegerField(source="leave_type_id", read_only=True)
    type_name = serializers.CharField(source="leave_type.name", read_only=True)
    employee_name = serializers.CharField(source="user.name", read_only=True)

    class Meta:
        model = LeaveRequest
        fields = [
            "id",
            "type_id",
            "type_name",
            "employee_name",
            "start_date",
            "end_date",
            "unit",
            "days",
            "reason",
            "status",
            "rejected_reason",
            "created_at",
        ]


class LeaveRequestCreateSerializer(serializers.Serializer):
    type_id = serializers.IntegerField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    unit = serializers.ChoiceField(choices=["full", "half_am", "half_pm"])
    reason = serializers.CharField(allow_blank=True, required=False, default="")

    def validate(self, attrs):
        if attrs["unit"] != "full":
            attrs["end_date"] = attrs["start_date"]
        if attrs["end_date"] < attrs["start_date"]:
            raise serializers.ValidationError("終了日は開始日以降を指定してください。")
        try:
            leave_type = LeaveType.objects.get(pk=attrs["type_id"], is_active=True)
        except LeaveType.DoesNotExist as exc:
            raise serializers.ValidationError({"type_id": "休暇種類が見つかりません。"}) from exc
        if leave_type.requires_reason and not attrs.get("reason"):
            raise serializers.ValidationError({"reason": "この休暇種類では理由が必須です。"})
        if attrs["unit"] != "full" and not leave_type.supports_half_day:
            raise serializers.ValidationError({"unit": "この休暇種類は半日取得に対応していません。"})
        attrs["leave_type"] = leave_type
        return attrs


class LeaveRejectSerializer(serializers.Serializer):
    reason = serializers.CharField(allow_blank=False)
