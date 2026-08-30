from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.common.models import TimeStampedModel


class BreakMode(models.TextChoices):
    """休憩の扱い。管理者が勤務体系ごとに切り替える（設計書 第5.1章）。"""

    AUTO_DEDUCT = "auto_deduct", "自動控除"
    PUNCH = "punch", "実打刻"


class DayType(models.TextChoices):
    BUSINESS = "business", "営業日"
    COMPANY_HOLIDAY = "company_holiday", "所定休日"
    STATUTORY_HOLIDAY = "statutory_holiday", "法定休日"


DEFAULT_BREAK_RULES = [
    {"over": 360, "deduct": 45},
    {"over": 480, "deduct": 60},
]


class WorkPattern(TimeStampedModel):
    """勤務体系マスタ。所定労働時間も休憩方式も管理画面から設定する。"""

    name = models.CharField("名称", max_length=60)
    break_mode = models.CharField(
        "休憩方式", max_length=12, choices=BreakMode.choices, default=BreakMode.AUTO_DEDUCT
    )
    break_rules = models.JSONField(
        "自動控除ルール",
        default=list,
        blank=True,
        help_text='例: [{"over": 360, "deduct": 45}, {"over": 480, "deduct": 60}]（拘束時間の分）',
    )
    scheduled_minutes = models.PositiveIntegerField(
        "所定労働時間（分）",
        default=480,
        validators=[MinValueValidator(1), MaxValueValidator(1440)],
    )
    start_time = models.TimeField("所定始業", null=True, blank=True)
    end_time = models.TimeField("所定終業", null=True, blank=True)
    holiday_dow = models.JSONField(
        "所定休日の曜日", default=list, blank=True, help_text="0=日曜 … 6=土曜。例: [0, 6]"
    )
    statutory_holiday_dow = models.PositiveSmallIntegerField(
        "法定休日の曜日", null=True, blank=True, help_text="0=日曜 … 6=土曜"
    )
    is_default = models.BooleanField("新規ユーザーの初期割当", default=False)

    class Meta:
        verbose_name = verbose_name_plural = "勤務体系"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.break_rules and self.break_mode == BreakMode.AUTO_DEDUCT:
            self.break_rules = list(DEFAULT_BREAK_RULES)
        super().save(*args, **kwargs)


class HolidayCalendar(models.Model):
    """会社カレンダー。国民の祝日はデータマイグレーションで配る（追補 第7.1章）。"""

    date = models.DateField("日付", primary_key=True)
    day_type = models.CharField(
        "区分", max_length=20, choices=DayType.choices, default=DayType.BUSINESS
    )
    name = models.CharField("名称", max_length=40, blank=True)

    class Meta:
        verbose_name = verbose_name_plural = "会社カレンダー"
        ordering = ["date"]

    def __str__(self) -> str:
        return f"{self.date} {self.get_day_type_display()} {self.name}".strip()


class RecordSource(models.TextChoices):
    PUNCH = "punch", "打刻"
    ADMIN_CORRECTION = "admin_correction", "管理者修正"


class TimeRecord(TimeStampedModel):
    """日次1件の打刻。設計書 第4章 time_record。"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="利用者", on_delete=models.CASCADE, related_name="time_records"
    )
    work_date = models.DateField("勤務日")
    clock_in_at = models.DateTimeField("出勤時刻", null=True, blank=True)
    clock_out_at = models.DateTimeField("退勤時刻", null=True, blank=True)
    day_type = models.CharField(
        "日区分", max_length=20, choices=DayType.choices, default=DayType.BUSINESS
    )
    source = models.CharField(
        "入力元", max_length=20, choices=RecordSource.choices, default=RecordSource.PUNCH
    )
    note = models.CharField("備考", max_length=200, blank=True)

    class Meta:
        verbose_name = verbose_name_plural = "打刻記録"
        ordering = ["-work_date"]
        constraints = [
            models.UniqueConstraint(fields=["user", "work_date"], name="uniq_time_record_user_date")
        ]

    def __str__(self) -> str:
        return f"{self.user} {self.work_date}"

    @property
    def is_open(self) -> bool:
        return self.clock_in_at is not None and self.clock_out_at is None


class BreakRecord(models.Model):
    """休憩の実打刻。休憩方式が「実打刻」のときのみ使う。"""

    time_record = models.ForeignKey(
        TimeRecord, verbose_name="打刻記録", on_delete=models.CASCADE, related_name="breaks"
    )
    start_at = models.DateTimeField("休憩開始")
    end_at = models.DateTimeField("休憩終了", null=True, blank=True)

    class Meta:
        verbose_name = verbose_name_plural = "休憩記録"
        ordering = ["start_at"]

    def __str__(self) -> str:
        return f"{self.time_record} 休憩 {self.start_at:%H:%M}"


class DailySummary(models.Model):
    """日次の計算結果を確定保存する。ビューからは常にこの値を参照する。"""

    time_record = models.OneToOneField(
        TimeRecord, verbose_name="打刻記録", on_delete=models.CASCADE, related_name="summary"
    )
    worked_minutes = models.PositiveIntegerField("実労働（分）", default=0)
    break_minutes = models.PositiveIntegerField("休憩（分）", default=0)
    overtime_within_legal = models.PositiveIntegerField("法定内残業（分）", default=0)
    overtime_statutory = models.PositiveIntegerField("法定外残業（分）", default=0)
    night_minutes = models.PositiveIntegerField("深夜労働（分）", default=0)
    holiday_minutes = models.PositiveIntegerField("休日労働（分）", default=0)
    warnings = models.JSONField("警告", default=list, blank=True)
    calculated_at = models.DateTimeField("計算日時", auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = "日次集計"

    def __str__(self) -> str:
        return f"{self.time_record} 集計"

    @property
    def agreement36_minutes(self) -> int:
        return self.overtime_statutory + self.holiday_minutes


class CorrectionStatus(models.TextChoices):
    PENDING = "pending", "承認待ち"
    APPROVED = "approved", "承認済み"
    REJECTED = "rejected", "差し戻し"


class TimeCorrectionRequest(TimeStampedModel):
    """打刻漏れ・修正の申請。承認時に time_record へ適用する。"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="利用者",
        on_delete=models.CASCADE,
        related_name="correction_requests",
    )
    work_date = models.DateField("対象日")
    requested_clock_in_at = models.DateTimeField("修正後の出勤時刻", null=True, blank=True)
    requested_clock_out_at = models.DateTimeField("修正後の退勤時刻", null=True, blank=True)
    reason = models.TextField("理由")
    status = models.CharField(
        "状態", max_length=20, choices=CorrectionStatus.choices, default=CorrectionStatus.PENDING
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="承認者",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    reviewed_at = models.DateTimeField("承認日時", null=True, blank=True)
    rejected_reason = models.CharField("差し戻し理由", max_length=300, blank=True)

    class Meta:
        verbose_name = verbose_name_plural = "打刻修正申請"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user} {self.work_date} 修正申請"


class MonthlyStatus(models.TextChoices):
    DRAFT = "draft", "作成中"
    SUBMITTED = "submitted", "申請中"
    APPROVED = "approved", "承認済み"


class MonthlyAttendance(TimeStampedModel):
    """月次締め。承認済みになった期間の time_record / daily_summary は変更不可にする。"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="利用者",
        on_delete=models.CASCADE,
        related_name="monthly_attendances",
    )
    year_month = models.CharField("対象年月", max_length=7, help_text="YYYY-MM")
    status = models.CharField(
        "状態", max_length=20, choices=MonthlyStatus.choices, default=MonthlyStatus.DRAFT
    )
    work_days = models.PositiveIntegerField("出勤日数", default=0)
    worked_minutes = models.PositiveIntegerField("実労働合計（分）", default=0)
    overtime_within_legal_minutes = models.PositiveIntegerField("法定内残業合計（分）", default=0)
    overtime_statutory_minutes = models.PositiveIntegerField("法定外残業合計（分）", default=0)
    night_minutes = models.PositiveIntegerField("深夜労働合計（分）", default=0)
    holiday_minutes = models.PositiveIntegerField("休日労働合計（分）", default=0)
    submitted_at = models.DateTimeField("申請日時", null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="承認者",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    approved_at = models.DateTimeField("承認日時", null=True, blank=True)
    locked_at = models.DateTimeField("ロック日時", null=True, blank=True)

    class Meta:
        verbose_name = verbose_name_plural = "月次勤怠"
        ordering = ["-year_month"]
        constraints = [
            models.UniqueConstraint(fields=["user", "year_month"], name="uniq_monthly_attendance_user_ym")
        ]

    def __str__(self) -> str:
        return f"{self.user} {self.year_month}"

    @property
    def overtime_36_minutes(self) -> int:
        return self.overtime_statutory_minutes + self.holiday_minutes
