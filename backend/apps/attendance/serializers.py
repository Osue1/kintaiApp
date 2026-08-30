from rest_framework import serializers

from .models import TimeCorrectionRequest


class PunchSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["in", "out", "break_start", "break_end"])


class CorrectionRequestCreateSerializer(serializers.Serializer):
    date = serializers.DateField()
    type = serializers.ChoiceField(choices=["clock_in", "clock_out"])
    corrected_time = serializers.CharField(max_length=5)  # "HH:MM"
    reason = serializers.CharField(allow_blank=False)

    def validate_corrected_time(self, value: str) -> str:
        import re

        if not re.fullmatch(r"[0-2]\d:[0-5]\d", value):
            raise serializers.ValidationError("時刻は HH:MM 形式で入力してください。")
        return value


class CorrectionRequestSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="user.name", read_only=True)

    class Meta:
        model = TimeCorrectionRequest
        fields = [
            "id",
            "employee_name",
            "work_date",
            "requested_clock_in_at",
            "requested_clock_out_at",
            "reason",
            "status",
            "rejected_reason",
            "created_at",
        ]


class RejectSerializer(serializers.Serializer):
    reason = serializers.CharField(allow_blank=False)
