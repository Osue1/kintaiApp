"""パスワード再設定のセルフサービスフロー。

設計書に明記はないが、これまで従業員がパスワードを忘れると管理者による手動再設定しか
手段がなかった実運用上の欠陥を埋める。他の書き込み系サービスと同様、ORMとの
やり取りだけをここで行い、パスワードの強度検証は Django 標準の validate_password に委譲する。

トークンはメール本文にのみ平文で載せ、DBにはSHA-256ハッシュだけを保存する
（漏洩時にトークンを復元できないようにするため）。有効期限を短く（既定30分）取り、
使用済みトークンの再利用や期限切れトークンの利用を弾く。
"""
import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import EmailMessage
from django.utils import timezone

from apps.accounts.models import PasswordResetToken

TOKEN_VALID_MINUTES = 30


class PasswordResetTokenError(Exception):
    """トークンが無効（存在しない・期限切れ・使用済み）な場合に送出する。"""


def request_password_reset(email: str, reset_url_base: str) -> None:
    """該当メールアドレスのユーザーが存在すればトークンを発行してメール送信する。

    該当ユーザーが存在するかどうかで呼び出し元の挙動を変えてはならない
    （メールアドレスの在不在を外部から推測できてしまう＝ユーザー列挙攻撃を防ぐため）。
    そのためこの関数は常に None を返し、例外も送出しない。呼び出し元(view)は
    ユーザーの有無に関わらず同一のレスポンスを返すこと。
    """
    user_model = get_user_model()
    user = user_model.objects.filter(email__iexact=email, is_active=True).first()
    if user is None:
        return

    raw_token = secrets.token_urlsafe(32)
    PasswordResetToken.objects.create(
        user=user,
        token_hash=_hash_token(raw_token),
        expires_at=timezone.now() + timedelta(minutes=TOKEN_VALID_MINUTES),
    )

    reset_link = f"{reset_url_base.rstrip('/')}?token={raw_token}"
    subject = "【勤怠管理システム】パスワード再設定のご案内"
    body = (
        f"{user.name} 様\n\n"
        "パスワード再設定のリクエストを受け付けました。\n"
        f"以下のリンクから新しいパスワードを設定してください（有効期限: 発行から{TOKEN_VALID_MINUTES}分）。\n\n"
        f"{reset_link}\n\n"
        "このリクエストに心当たりがない場合は、本メールを破棄してください。"
        "パスワードは変更されません。\n"
    )
    EmailMessage(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email]).send()


def confirm_password_reset(token: str, new_password: str) -> None:
    """トークンを検証し、問題なければ新しいパスワードを設定する。

    同一ユーザーに対する他の未使用トークンも合わせて失効させる（1回の再設定で
    それ以前に発行された全てのリンクを無効化し、古いリンクの使い回しを防ぐ）。
    """
    reset_token = PasswordResetToken.objects.select_related("user").filter(
        token_hash=_hash_token(token)
    ).first()
    if reset_token is None:
        raise PasswordResetTokenError("このリンクは無効です。もう一度パスワード再設定をリクエストしてください。")
    if reset_token.used_at is not None:
        raise PasswordResetTokenError("このリンクは既に使用済みです。もう一度パスワード再設定をリクエストしてください。")
    if reset_token.expires_at < timezone.now():
        raise PasswordResetTokenError("このリンクの有効期限が切れています。もう一度パスワード再設定をリクエストしてください。")

    user = reset_token.user
    try:
        validate_password(new_password, user=user)
    except DjangoValidationError as exc:
        raise PasswordResetTokenError(" ".join(exc.messages)) from exc

    user.set_password(new_password)
    user.save(update_fields=["password"])

    now = timezone.now()
    reset_token.used_at = now
    reset_token.save(update_fields=["used_at"])
    # このユーザー宛の他の未使用トークンも道連れで失効させる（古いメールのリンクを
    # 使われても再設定できないようにする）。
    PasswordResetToken.objects.filter(user=user, used_at__isnull=True).exclude(pk=reset_token.pk).update(
        used_at=now
    )


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
