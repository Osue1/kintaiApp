from django.contrib import admin

from apps.common.admin import SubtitleAdminMixin

from .models import (
    DailySummary,
    HolidayCalendar,
    MonthlyAttendance,
    TimeCorrectionRequest,
    TimeRecord,
    WorkPattern,
)


@admin.register(WorkPattern)
class WorkPatternAdmin(SubtitleAdminMixin, admin.ModelAdmin):
    changelist_subtitle = (
        "所定労働時間・休憩の取り方・休日の曜日を決める勤務体系マスタ。従業員ごとに1つ割り当てる"
        "（従業員管理画面から割当）。「新規ユーザーの初期割当」がONのものが、割当を忘れたときの"
        "既定値になる。「所定休日」は会社が決めた休みの曜日、「法定休日」は労基法で週1日以上"
        "必要な休日（この曜日の労働は法定休日労働として扱われる）。"
    )
    list_display = ["name", "break_mode", "scheduled_minutes", "statutory_holiday_dow", "is_default"]
    list_filter = ["break_mode", "is_default"]
    fieldsets = (
        (None, {"fields": ("name", "is_default")}),
        ("所定労働", {"fields": ("scheduled_minutes", "start_time", "end_time")}),
        ("休憩", {"fields": ("break_mode", "break_rules")}),
        ("休日", {"fields": ("holiday_dow", "statutory_holiday_dow")}),
    )


@admin.register(HolidayCalendar)
class HolidayCalendarAdmin(SubtitleAdminMixin, admin.ModelAdmin):
    changelist_subtitle = (
        "会社カレンダー（営業日・国民の祝日・会社独自の休業日）。国民の祝日は自動投入済みだが、"
        "夏季休業・年末年始などの会社独自の休みはここに追加する。ここに登録した日は"
        "勤怠集計で休日として扱われる。"
    )
    list_display = ["date", "day_type", "name"]
    list_filter = ["day_type"]
    date_hierarchy = "date"


class DailySummaryInline(admin.StackedInline):
    model = DailySummary
    extra = 0


@admin.register(TimeRecord)
class TimeRecordAdmin(admin.ModelAdmin):
    list_display = ["user", "work_date", "clock_in_at", "clock_out_at", "day_type", "source"]
    list_filter = ["day_type", "source"]
    search_fields = ["user__name"]
    date_hierarchy = "work_date"
    inlines = [DailySummaryInline]


@admin.register(TimeCorrectionRequest)
class TimeCorrectionRequestAdmin(admin.ModelAdmin):
    list_display = ["user", "work_date", "status", "created_at"]
    list_filter = ["status"]
    search_fields = ["user__name"]


@admin.register(MonthlyAttendance)
class MonthlyAttendanceAdmin(admin.ModelAdmin):
    list_display = ["user", "year_month", "status", "work_days", "worked_minutes", "locked_at"]
    list_filter = ["status"]
    search_fields = ["user__name"]
