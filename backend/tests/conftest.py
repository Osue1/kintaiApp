import pytest
from django.contrib.auth import get_user_model

from apps.accounts.models import Company, Role
from apps.attendance.models import BreakMode, WorkPattern


@pytest.fixture(autouse=True)
def _isolate_media_root(tmp_path, settings):
    """請求書PDF生成等のテストが実ファイルを書き出す先を、テストごとの一時ディレクトリに
    差し替える。DBはトランザクションのロールバックでテスト間を分離できるが、
    ファイルシステムへの書き込みはそれでは戻らないため、対策しないと
    backend/media/invoices/ 配下に実行のたびPDFが際限なく蓄積してしまう
    （実際に過去のテスト実行分が20件以上残っていた実害を確認して追加した）。
    """
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture(autouse=True)
def _disable_basic_auth_by_default(settings):
    """開発者のローカルシェルにBASIC_AUTH_USER/PASSWORDが設定されていても、
    テストの合否がそれに左右されないようにする（apps/common/middleware.py）。

    実際にこの対策を入れる前、開発者のシェル環境変数にBASIC_AUTH_USER/
    PASSWORDが残っていたせいで、Basic認証と無関係な既存テストが軒並み
    401で落ちる実害が起きた。Basic認証自体を試験したいテストは、各テスト
    内で settings.BASIC_AUTH_USER 等を明示的に上書きすること
    （tests/test_basic_auth_middleware.py 参照）。
    """
    settings.BASIC_AUTH_USER = ""
    settings.BASIC_AUTH_PASSWORD = ""


@pytest.fixture
def company(db) -> Company:
    return Company.objects.create(name="株式会社テスト", invoice_reg_no="T1234567890123")


@pytest.fixture
def work_pattern(db) -> WorkPattern:
    return WorkPattern.objects.create(
        name="標準（週休2日）",
        break_mode=BreakMode.AUTO_DEDUCT,
        scheduled_minutes=480,
        holiday_dow=[0, 6],
        statutory_holiday_dow=0,
        is_default=True,
    )


@pytest.fixture
def employee(db, work_pattern):
    return get_user_model().objects.create_user(
        email="employee@example.com",
        password="correct-horse-battery",
        name="山田太郎",
        role=Role.EMPLOYEE,
        work_pattern=work_pattern,
    )


@pytest.fixture
def admin_user(db, work_pattern):
    return get_user_model().objects.create_user(
        email="admin@example.com",
        password="correct-horse-battery",
        name="管理者",
        role=Role.ADMIN,
        work_pattern=work_pattern,
    )
