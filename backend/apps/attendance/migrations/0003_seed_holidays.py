"""国民の祝日を投入する（設計書 第4章「環境分離での法令マスタの扱い」）。

祝日は法令で決まる値なので管理画面から編集させず、データマイグレーションに含める。
祝日法の改正があればこのファイルの対象年を延長してデプロイするだけで全環境に反映される。
"""
import jpholiday
from django.db import migrations

YEARS = range(2024, 2029)


def seed(apps, schema_editor):
    HolidayCalendar = apps.get_model("attendance", "HolidayCalendar")
    rows = [
        HolidayCalendar(date=d, day_type="company_holiday", name=name)
        for year in YEARS
        for d, name in jpholiday.year_holidays(year)
    ]
    HolidayCalendar.objects.bulk_create(rows, ignore_conflicts=True)


def unseed(apps, schema_editor):
    HolidayCalendar = apps.get_model("attendance", "HolidayCalendar")
    dates = [d for year in YEARS for d, _ in jpholiday.year_holidays(year)]
    HolidayCalendar.objects.filter(date__in=dates).delete()


class Migration(migrations.Migration):
    dependencies = [("attendance", "0002_timecorrectionrequest_timerecord_dailysummary_and_more")]

    operations = [migrations.RunPython(seed, unseed)]
