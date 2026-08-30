from django.contrib import admin

from .models import (
    DailySummary,
    HolidayCalendar,
    MonthlyAttendance,
    TimeCorrectionRequest,
    TimeRecord,
    WorkPattern,
)


@admin.register(WorkPattern)
class WorkPatternAdmin(admin.ModelAdmin):
    list_display = ["name", "break_mode", "scheduled_minutes", "statutory_holiday_dow", "is_default"]
    list_filter = ["break_mode", "is_default"]
    fieldsets = (
        (None, {"fields": ("name", "is_default")}),
        ("所定労働", {"fields": ("scheduled_minutes", "start_time", "end_time")}),
        ("休憩", {"fields": ("break_mode", "break_rules")}),
        ("休日", {"fields": ("holiday_dow", "statutory_holiday_dow")}),
    )


@admin.register(HolidayCalendar)
class HolidayCalendarAdmin(admin.ModelAdmin):
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
