"""法令で決まる税制マスタを投入する（設計書 第4章「環境分離での法令マスタの扱い」）。

税率・源泉徴収率・免税事業者の控除率は管理画面から編集させず、データマイグレーションで
コードに含める。法改正（2026-10-01 の控除率切替など）はこのファイルへの追記とデプロイで
全環境に反映する。
"""
from datetime import date
from decimal import Decimal

from django.db import migrations


def seed(apps, schema_editor):
    TaxRate = apps.get_model("billing", "TaxRate")
    ExemptDeductionRate = apps.get_model("billing", "ExemptDeductionRate")
    WithholdingRule = apps.get_model("billing", "WithholdingRule")

    TaxRate.objects.get_or_create(
        category="standard",
        effective_from=date(2019, 10, 1),
        defaults={"rate_percent": Decimal("10.00"), "effective_to": None},
    )
    TaxRate.objects.get_or_create(
        category="reduced",
        effective_from=date(2019, 10, 1),
        defaults={"rate_percent": Decimal("8.00"), "effective_to": None},
    )
    TaxRate.objects.get_or_create(
        category="exempt",
        effective_from=date(2019, 10, 1),
        defaults={"rate_percent": Decimal("0.00"), "effective_to": None},
    )

    # 免税事業者からの仕入に対する経過措置控除率（設計書 第8.4章）
    ExemptDeductionRate.objects.get_or_create(
        effective_from=date(2023, 10, 1),
        defaults={"deduction_percent": Decimal("80.00"), "effective_to": date(2026, 9, 30)},
    )
    ExemptDeductionRate.objects.get_or_create(
        effective_from=date(2026, 10, 1),
        defaults={"deduction_percent": Decimal("50.00"), "effective_to": date(2029, 9, 30)},
    )
    ExemptDeductionRate.objects.get_or_create(
        effective_from=date(2029, 10, 1),
        defaults={"deduction_percent": Decimal("0.00"), "effective_to": None},
    )

    WithholdingRule.objects.get_or_create(
        effective_from=date(2013, 1, 1),
        defaults={
            "threshold_amount": Decimal("1000000"),
            "rate_below_percent": Decimal("10.21"),
            "rate_above_percent": Decimal("20.42"),
            "effective_to": None,
        },
    )


def unseed(apps, schema_editor):
    apps.get_model("billing", "TaxRate").objects.all().delete()
    apps.get_model("billing", "ExemptDeductionRate").objects.all().delete()
    apps.get_model("billing", "WithholdingRule").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("billing", "0001_initial")]

    operations = [migrations.RunPython(seed, unseed)]
