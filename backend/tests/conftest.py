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
