from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models

from apps.common.models import TimeStampedModel


class Role(models.TextChoices):
    ADMIN = "admin", "管理者"
    EMPLOYEE = "employee", "正社員"


class RoundingMode(models.TextChoices):
    FLOOR = "floor", "切り捨て"
    ROUND = "round", "四捨五入"
    CEIL = "ceil", "切り上げ"


class Company(TimeStampedModel):
    """会社設定。各環境に1行のみ（追補: 1契約=1環境）。"""

    name = models.CharField("会社名", max_length=120)
    address = models.CharField("住所", max_length=255, blank=True)
    representative = models.CharField("代表者名", max_length=60, blank=True)
    invoice_reg_no = models.CharField(
        "インボイス登録番号", max_length=14, blank=True, help_text="T + 13桁"
    )
    rounding_mode = models.CharField(
        "消費税の端数処理", max_length=10, choices=RoundingMode.choices, default=RoundingMode.FLOOR
    )
    logo_key = models.CharField("ロゴのオブジェクトキー", max_length=255, blank=True)

    class Meta:
        verbose_name = verbose_name_plural = "会社設定"

    def __str__(self) -> str:
        return self.name

    @classmethod
    def get_solo(cls) -> "Company":
        """各環境に1行だけ存在する会社設定を返す。無ければ作る。"""
        obj = cls.objects.order_by("pk").first()
        if obj is None:
            obj = cls.objects.create(name="未設定")
        return obj


class Team(TimeStampedModel):
    """社員が属するグループ（部署・チーム）。出勤状況画面の既定の絞り込み単位。"""

    name = models.CharField("グループ名", max_length=60)

    class Meta:
        verbose_name = verbose_name_plural = "グループ"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email: str, password: str | None = None, **extra):
        if not email:
            raise ValueError("メールアドレスは必須です。")
        user = self.model(email=self.normalize_email(email), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra):
        extra.setdefault("role", Role.ADMIN)
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("name", "管理者")
        return self.create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    email = models.EmailField("メールアドレス", max_length=254, unique=True)
    name = models.CharField("氏名", max_length=60)
    role = models.CharField("区分", max_length=10, choices=Role.choices, default=Role.EMPLOYEE)
    work_pattern = models.ForeignKey(
        "attendance.WorkPattern",
        verbose_name="勤務体系",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="users",
    )
    leave_policy = models.ForeignKey(
        "leave.PaidLeavePolicy",
        verbose_name="有給ポリシー",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="users",
    )
    team = models.ForeignKey(
        Team,
        verbose_name="グループ",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="members",
    )
    hire_date = models.DateField("入社日", null=True, blank=True)
    retired_at = models.DateField("退職日", null=True, blank=True)
    is_active = models.BooleanField("有効", default=True)
    is_staff = models.BooleanField("Django管理サイトを使える", default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    class Meta:
        verbose_name = verbose_name_plural = "利用者"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} <{self.email}>"

    @property
    def is_admin_role(self) -> bool:
        return self.role == Role.ADMIN


class AuditLog(models.Model):
    """承認・打刻修正・マスタ変更・請求書発行を記録する（設計書 第12.1章）。"""

    actor = models.ForeignKey(
        User, verbose_name="操作者", on_delete=models.SET_NULL, null=True, related_name="audit_logs"
    )
    action = models.CharField("操作", max_length=60)
    target_type = models.CharField("対象種別", max_length=60)
    target_id = models.BigIntegerField("対象ID", null=True, blank=True)
    before = models.JSONField("変更前", null=True, blank=True)
    after = models.JSONField("変更後", null=True, blank=True)
    ip = models.GenericIPAddressField("IP", null=True, blank=True)
    user_agent = models.TextField("User-Agent", blank=True)
    created_at = models.DateTimeField("日時", auto_now_add=True)

    class Meta:
        verbose_name = verbose_name_plural = "監査ログ"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["target_type", "target_id"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.action} {self.target_type}#{self.target_id}"


class PasswordResetToken(models.Model):
    """パスワード再設定トークン（セルフサービスでの再設定を可能にする）。

    これまで従業員がパスワードを忘れると管理者に手動で再設定してもらうしかなく、
    セルフサービスの手段が存在しなかった。トークンは平文をDBに保存せずSHA-256の
    ハッシュ値だけを保存する（DBが漏洩してもトークンを復元してなりすまし再設定
    できないようにするため。セッションキーの扱いと同じ考え方）。
    """

    user = models.ForeignKey(
        User, verbose_name="対象ユーザー", on_delete=models.CASCADE, related_name="password_reset_tokens"
    )
    token_hash = models.CharField("トークンのSHA-256ハッシュ", max_length=64)
    created_at = models.DateTimeField("発行日時", auto_now_add=True)
    expires_at = models.DateTimeField("有効期限")
    used_at = models.DateTimeField("使用日時", null=True, blank=True)

    class Meta:
        verbose_name = verbose_name_plural = "パスワード再設定トークン"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["token_hash"])]

    def __str__(self) -> str:
        return f"{self.user} 宛のトークン（{self.created_at:%Y-%m-%d %H:%M} 発行）"
