"""労働時間計算のテーブル駆動テスト。

ケース表がそのまま仕様書の役割を果たす（設計書 第13章）。
DB を使わないので pytest.mark.django_db は不要。
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from apps.attendance.services.worktime import (
    BreakMode,
    BreakRule,
    DayType,
    InvalidPunchError,
    PunchInput,
    WorkPatternSpec,
    calculate_daily,
    night_overlap_minutes,
    required_break_minutes,
    resolve_auto_break,
)

JST = ZoneInfo("Asia/Tokyo")


def dt(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 9, day, hour, minute, tzinfo=JST)


STANDARD = WorkPatternSpec(
    scheduled_minutes=480,
    break_mode=BreakMode.AUTO_DEDUCT,
    break_rules=(BreakRule(360, 45), BreakRule(480, 60)),
)
SHORT = WorkPatternSpec(
    scheduled_minutes=360,
    break_mode=BreakMode.AUTO_DEDUCT,
    break_rules=(BreakRule(360, 45), BreakRule(480, 60)),
)
PUNCH_MODE = WorkPatternSpec(scheduled_minutes=480, break_mode=BreakMode.PUNCH)


@pytest.mark.parametrize(
    ("label", "punch", "pattern", "expected"),
    [
        (
            "所定どおり 9-18（拘束9h→60分控除で実働8h）",
            PunchInput(dt(1, 9), dt(1, 18)),
            STANDARD,
            {"worked": 480, "break": 60, "within": 0, "statutory": 0, "night": 0, "holiday": 0},
        ),
        (
            "拘束6時間ちょうど（控除なし）",
            PunchInput(dt(1, 9), dt(1, 15)),
            STANDARD,
            {"worked": 360, "break": 0, "within": 0, "statutory": 0, "night": 0, "holiday": 0},
        ),
        (
            "拘束6時間を1分超える（45分控除）",
            PunchInput(dt(1, 9), dt(1, 15, 1)),
            STANDARD,
            {"worked": 316, "break": 45, "within": 0, "statutory": 0, "night": 0, "holiday": 0},
        ),
        (
            "残業あり 9-21（実働11時間→法定外3時間）",
            PunchInput(dt(1, 9), dt(1, 21)),
            STANDARD,
            {"worked": 660, "break": 60, "within": 0, "statutory": 180, "night": 0, "holiday": 0},
        ),
        (
            "短時間勤務体系での法定内残業（所定6h・実働8h）",
            PunchInput(dt(1, 9), dt(1, 18)),
            SHORT,
            {"worked": 480, "break": 60, "within": 120, "statutory": 0, "night": 0, "holiday": 0},
        ),
        (
            "日跨ぎ 20:00-翌02:00（深夜4時間）",
            PunchInput(dt(1, 20), dt(2, 2)),
            STANDARD,
            {"worked": 360, "break": 0, "within": 0, "statutory": 0, "night": 240, "holiday": 0},
        ),
        (
            "法定休日の出勤は残業ではなく休日労働",
            PunchInput(dt(6, 9), dt(6, 18), day_type=DayType.STATUTORY_HOLIDAY),
            STANDARD,
            {"worked": 480, "break": 60, "within": 0, "statutory": 0, "night": 0, "holiday": 480},
        ),
    ],
)
def test_calculate_daily(label, punch, pattern, expected):
    result = calculate_daily(punch, pattern)
    assert result.worked_minutes == expected["worked"], label
    assert result.break_minutes == expected["break"], label
    assert result.overtime_within_legal == expected["within"], label
    assert result.overtime_statutory == expected["statutory"], label
    assert result.night_minutes == expected["night"], label
    assert result.holiday_minutes == expected["holiday"], label


def test_break_punch_mode_sums_actual_breaks():
    punch = PunchInput(
        dt(1, 9),
        dt(1, 19),
        breaks=((dt(1, 12), dt(1, 13)), (dt(1, 15), dt(1, 15, 15))),
    )
    result = calculate_daily(punch, PUNCH_MODE)
    assert result.break_minutes == 75
    assert result.worked_minutes == 525
    assert result.overtime_statutory == 45
    assert result.warnings == ()


def test_break_punch_mode_warns_when_below_legal_minimum():
    """保存は許可し、承認時にブロックする方針なので例外にはしない（設計書 第5.1章）。"""
    punch = PunchInput(dt(1, 9), dt(1, 19), breaks=((dt(1, 12), dt(1, 12, 30)),))
    result = calculate_daily(punch, PUNCH_MODE)
    assert result.break_minutes == 30
    assert len(result.warnings) == 1
    assert "労働基準法34条" in result.warnings[0]


def test_agreement36_target_excludes_within_legal_overtime():
    """36協定の集計対象は法定外残業＋法定休日労働のみ。"""
    result = calculate_daily(PunchInput(dt(1, 9), dt(1, 18)), SHORT)
    assert result.overtime_within_legal == 120
    assert result.agreement36_minutes == 0


def test_holiday_work_counts_toward_agreement36():
    result = calculate_daily(
        PunchInput(dt(6, 9), dt(6, 18), day_type=DayType.STATUTORY_HOLIDAY), STANDARD
    )
    assert result.agreement36_minutes == 480


@pytest.mark.parametrize(
    ("span", "expected"),
    [(360, 0), (361, 45), (480, 45), (481, 60), (600, 60)],
)
def test_resolve_auto_break_boundaries(span, expected):
    rules = (BreakRule(360, 45), BreakRule(480, 60))
    assert resolve_auto_break(span, rules) == expected


@pytest.mark.parametrize(
    ("worked", "expected"),
    [(360, 0), (361, 45), (480, 45), (481, 60)],
)
def test_required_break_boundaries(worked, expected):
    assert required_break_minutes(worked) == expected


def test_night_overlap_across_two_nights():
    """48時間近い拘束でも両方の深夜帯を拾う。"""
    minutes = night_overlap_minutes(dt(1, 21), dt(3, 6))
    # 1日目 22:00-翌05:00 = 420、2日目 22:00-翌05:00 = 420
    assert minutes == 840


def test_night_overlap_none_for_daytime():
    assert night_overlap_minutes(dt(1, 9), dt(1, 18)) == 0


def test_punch_break_in_night_is_excluded():
    punch = PunchInput(
        dt(1, 21), dt(2, 6), breaks=((dt(2, 0), dt(2, 1)),)
    )
    result = calculate_daily(punch, PUNCH_MODE)
    # 深夜帯 22:00-05:00 の7時間から、深夜にとった休憩1時間を引く
    assert result.night_minutes == 360


def test_clock_out_before_clock_in_raises():
    with pytest.raises(InvalidPunchError):
        calculate_daily(PunchInput(dt(1, 18), dt(1, 9)), STANDARD)


def test_break_longer_than_span_is_clamped():
    punch = PunchInput(dt(1, 9), dt(1, 10), breaks=((dt(1, 8), dt(1, 12)),))
    result = calculate_daily(punch, PUNCH_MODE)
    assert result.break_minutes == 60
    assert result.worked_minutes == 0


def test_minute_precision_is_preserved():
    """丸めは行わない。1分単位でそのまま保持する。"""
    punch = PunchInput(dt(1, 9, 3), dt(1, 18, 7))
    result = calculate_daily(punch, STANDARD)
    assert result.worked_minutes == 544 - 60
    assert timedelta(minutes=result.worked_minutes) == timedelta(hours=8, minutes=4)
