from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.audit import record_audit
from apps.common.permissions import IsAdminRole

from .models import Company, Team, User
from .serializers import (
    CompanyBriefSerializer,
    EmployeeCreateSerializer,
    EmployeeSerializer,
    EmployeeUpdateSerializer,
    LeavePolicyBriefSerializer,
    LoginSerializer,
    MeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    TeamBriefSerializer,
    WorkPatternBriefSerializer,
)
from .services.password_reset import (
    PasswordResetTokenError,
    confirm_password_reset,
    request_password_reset,
)


class LoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=LoginSerializer, responses={200: MeSerializer}, summary="ログイン")
    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request,
            username=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        if user is None:
            return Response(
                {
                    "code": "invalid_credentials",
                    "message": "メールアドレスまたはパスワードが違います。",
                    "field_errors": {},
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )
        login(request, user)
        get_token(request)  # ログイン直後に CSRF トークンを載せ替える
        return Response(MeSerializer(user).data)


class LogoutView(APIView):
    @extend_schema(request=None, responses={204: None}, summary="ログアウト")
    def post(self, request: Request) -> Response:
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetRequestView(APIView):
    """パスワード再設定メールの送信依頼。未ログイン状態から呼べる必要があるため AllowAny。

    メールアドレスの在不在に関わらず常に同じレスポンス（204）を返す
    （在不在で応答が変わると第三者がメールアドレスの登録有無を調べられてしまうため）。
    """

    permission_classes = [AllowAny]

    @extend_schema(request=PasswordResetRequestSerializer, responses={204: None}, summary="パスワード再設定メールを送信")
    def post(self, request: Request) -> Response:
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_password_reset(
            serializer.validated_data["email"], serializer.validated_data["reset_url_base"]
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetConfirmView(APIView):
    """トークンを検証し、新しいパスワードを設定する。ログイン不要（AllowAny）。"""

    permission_classes = [AllowAny]

    @extend_schema(request=PasswordResetConfirmSerializer, responses={204: None}, summary="パスワードを再設定")
    def post(self, request: Request) -> Response:
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            confirm_password_reset(serializer.validated_data["token"], serializer.validated_data["password"])
        except PasswordResetTokenError as exc:
            return Response({"code": "invalid_token", "message": str(exc), "field_errors": {}}, status=400)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: MeSerializer}, summary="ログイン中のユーザー")
    def get(self, request: Request) -> Response:
        data = MeSerializer(request.user).data
        data["company"] = CompanyBriefSerializer(Company.get_solo()).data
        return Response(data)


class CsrfView(APIView):
    """SPA が最初に叩いて CSRF Cookie を受け取るためのエンドポイント。"""

    permission_classes = [AllowAny]

    @extend_schema(responses={204: None}, summary="CSRFトークンの発行")
    def get(self, request: Request) -> Response:
        get_token(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class EmployeeOptionsView(APIView):
    """従業員登録フォームの選択肢（勤務体系・有給ポリシー）。"""

    permission_classes = [IsAuthenticated, IsAdminRole]

    @extend_schema(summary="勤務体系・有給ポリシー・グループの選択肢")
    def get(self, request: Request) -> Response:
        from apps.attendance.models import WorkPattern
        from apps.leave.models import PaidLeavePolicy

        return Response(
            {
                "work_patterns": WorkPatternBriefSerializer(WorkPattern.objects.all(), many=True).data,
                "leave_policies": LeavePolicyBriefSerializer(PaidLeavePolicy.objects.all(), many=True).data,
                "teams": TeamBriefSerializer(Team.objects.all(), many=True).data,
            }
        )


class EmployeeListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    @extend_schema(responses={200: EmployeeSerializer}, summary="従業員の一覧")
    def get(self, request: Request) -> Response:
        qs = User.objects.select_related("work_pattern", "leave_policy", "team").all()
        return Response(EmployeeSerializer(qs, many=True).data)

    @extend_schema(request=EmployeeCreateSerializer, responses={201: EmployeeSerializer}, summary="従業員を登録")
    def post(self, request: Request) -> Response:
        serializer = EmployeeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = User.objects.create_user(
            email=data["email"],
            password=data["password"],
            name=data["name"],
            role=data["role"],
            hire_date=data.get("hire_date"),
            team=data.get("team"),
            work_pattern=data.get("work_pattern"),
            leave_policy=data.get("leave_policy"),
        )
        record_audit(
            request, "employee_create", "User", user.id,
            after={"email": user.email, "name": user.name, "role": user.role},
        )
        return Response(EmployeeSerializer(user).data, status=201)


class EmployeeDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    @extend_schema(request=EmployeeUpdateSerializer, responses={200: EmployeeSerializer}, summary="従業員を更新")
    def patch(self, request: Request, pk: int) -> Response:
        target = get_object_or_404(User, pk=pk)
        serializer = EmployeeUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if target.id == request.user.id and data.get("is_active") is False:
            return Response(
                {"code": "invalid", "message": "自分自身を無効化することはできません。", "field_errors": {}},
                status=400,
            )

        password = data.pop("password", None)
        before = {field: getattr(target, field) for field in data}
        for field, value in data.items():
            setattr(target, field, value)
        if password:
            target.set_password(password)
        target.save()
        after = {field: getattr(target, field) for field in data}
        record_audit(
            request, "employee_update", "User", target.id,
            before={k: str(v) for k, v in before.items()},
            after={k: str(v) for k, v in after.items()},
        )
        return Response(EmployeeSerializer(target).data)
