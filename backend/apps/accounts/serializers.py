from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.attendance.models import WorkPattern
from apps.leave.models import PaidLeavePolicy

from .models import AuditLog, Company, Role, Team, User


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(label="メールアドレス")
    password = serializers.CharField(label="パスワード", write_only=True, style={"input_type": "password"})


class AuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.name", read_only=True, default=None)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "actor_name",
            "action",
            "target_type",
            "target_id",
            "before",
            "after",
            "ip",
            "user_agent",
            "created_at",
        ]


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(label="メールアドレス")
    # フロントのオリジンをここで受け取り、メール本文のリンクをそのオリジン向けに組み立てる
    # （バックエンド側でSPAのURLをハードコードしないため）。
    reset_url_base = serializers.URLField(label="再設定ページのURL")


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(label="トークン")
    password = serializers.CharField(label="新しいパスワード", write_only=True)


class CompanyBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ["id", "name", "invoice_reg_no"]


class MeSerializer(serializers.ModelSerializer):
    is_admin = serializers.BooleanField(source="is_admin_role", read_only=True)
    work_pattern_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "name", "role", "is_admin", "hire_date", "work_pattern_id"]


class WorkPatternBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkPattern
        fields = ["id", "name"]


class LeavePolicyBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaidLeavePolicy
        fields = ["id", "name"]


class TeamBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ["id", "name"]


class EmployeeSerializer(serializers.ModelSerializer):
    is_admin = serializers.BooleanField(source="is_admin_role", read_only=True)
    work_pattern_name = serializers.CharField(source="work_pattern.name", read_only=True, default=None)
    leave_policy_name = serializers.CharField(source="leave_policy.name", read_only=True, default=None)
    team_name = serializers.CharField(source="team.name", read_only=True, default=None)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "name",
            "role",
            "is_admin",
            "hire_date",
            "retired_at",
            "is_active",
            "team",
            "team_name",
            "work_pattern",
            "work_pattern_name",
            "leave_policy",
            "leave_policy_name",
        ]


class EmployeeCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    name = serializers.CharField(max_length=60)
    password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=Role.choices, default=Role.EMPLOYEE)
    hire_date = serializers.DateField(required=False, allow_null=True, default=None)
    team = serializers.PrimaryKeyRelatedField(queryset=Team.objects.all(), required=False, allow_null=True, default=None)
    work_pattern = serializers.PrimaryKeyRelatedField(
        queryset=WorkPattern.objects.all(), required=False, allow_null=True, default=None
    )
    leave_policy = serializers.PrimaryKeyRelatedField(
        queryset=PaidLeavePolicy.objects.all(), required=False, allow_null=True, default=None
    )

    def validate_email(self, value: str) -> str:
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("このメールアドレスは既に使用されています。")
        return value

    def validate_password(self, value: str) -> str:
        validate_password(value)
        return value


class EmployeeUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=60, required=False)
    role = serializers.ChoiceField(choices=Role.choices, required=False)
    hire_date = serializers.DateField(required=False, allow_null=True)
    retired_at = serializers.DateField(required=False, allow_null=True)
    is_active = serializers.BooleanField(required=False)
    team = serializers.PrimaryKeyRelatedField(queryset=Team.objects.all(), required=False, allow_null=True)
    work_pattern = serializers.PrimaryKeyRelatedField(
        queryset=WorkPattern.objects.all(), required=False, allow_null=True
    )
    leave_policy = serializers.PrimaryKeyRelatedField(
        queryset=PaidLeavePolicy.objects.all(), required=False, allow_null=True
    )
    password = serializers.CharField(write_only=True, required=False)

    def validate_password(self, value: str) -> str:
        validate_password(value)
        return value
