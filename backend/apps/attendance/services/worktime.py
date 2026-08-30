"""1日の労働時間を計算する純関数。

ここに Django のモデルは持ち込まない。入力は値オブジェクト、出力は計算結果だけ。
ビューからもバッチからも同じ関数を呼び、テストはこの層に集中させる
（設計書 第3.2章・第13章）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from enum import StrEnum

# 労働基準法32条の法定労働時間
LEGAL_DAILY_MINUTES = 480
# 深夜割増の時間帯（労働基準法37条4項）
NIGHT_START = time(22, 0)
NIGHT_END = time(5, 0)
# 労働基準法34条の最低休憩
MIN_BREAK_RULES = ((480, 60), (360, 45))  # (労働時間がこれを超えたら, 必要な休憩分)


class BreakMode(StrEnum):
    AUTO_DEDUCT = "auto_deduct"
    PUNCH = "punch"


class DayType(StrEnum):
    BUSINESS = "business"
    COMPANY_HOLIDAY = "company_holiday"
    STATUTORY_HOLIDAY = "statutory_holiday"


@dataclass(frozen=True, slots=True)
class BreakRule:
    """拘束時間が over_minutes を超えたら deduct_minutes を控除する。"""

    over_minutes: int
    deduct_minutes: int


@dataclass(frozen=True, slots=True)
class WorkPatternSpec:
    scheduled_minutes: int = LEGAL_DAILY_MINUTES
    break_mode: BreakMode = BreakMode.AUTO_DEDUCT
    break_rules: tuple[BreakRule, ...] = ()


@dataclass(frozen=True, slots=True)
class PunchInput:
    clock_in_at: datetime
    clock_out_at: datetime
    breaks: tuple[tuple[datetime, datetime], ...] = ()
    day_type: DayType = DayType.BUSINESS


@dataclass(frozen=True, slots=True)
class DailyCalculation:
    worked_minutes: int
    break_minutes: int
    overtime_within_legal: int
    overtime_statutory: int
    night_minutes: int
    holiday_minutes: int
    warnings: tuple[str, ...] = field(default=())

    @property
    def agreement36_minutes(self) -> int:
        """36協定の集計対象＝法定外残業＋法定休日労働（設計書 第5.2章）。"""
        return self.overtime_statutory + self.holiday_minutes


class InvalidPunchError(ValueError):
    """打刻の前後関係が壊れている。"""


def _minutes(delta: timedelta) -> int:
    return int(delta.total_seconds() // 60)


def _overlap_minutes(
    a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime
) -> int:
    start = max(a_start, b_start)
    end = min(a_end, b_end)
    return _minutes(end - start) if end > start else 0


def resolve_auto_break(span_minutes: int, rules: tuple[BreakRule, ...]) -> int:
    """拘束時間に対して適用される自動控除分を返す。

    複数のルールに該当する場合は、最も長い控除を採用する。
    """
    if not rules:
        rules = tuple(BreakRule(over, deduct) for over, deduct in MIN_BREAK_RULES)
    applicable = [r.deduct_minutes for r in rules if span_minutes > r.over_minutes]
    return max(applicable) if applicable else 0


def night_overlap_minutes(start: datetime, end: datetime) -> int:
    """22:00〜翌05:00 と重なる分数。日をまたぐ勤務にも対応する。"""
    if end <= start:
        return 0
    total = 0
    day = start.date() - timedelta(days=1)
    last = end.date()
    while day <= last:
        night_start = datetime.combine(day, NIGHT_START, tzinfo=start.tzinfo)
        night_end = datetime.combine(day + timedelta(days=1), NIGHT_END, tzinfo=start.tzinfo)
        total += _overlap_minutes(start, end, night_start, night_end)
        day += timedelta(days=1)
    return total


def required_break_minutes(worked_minutes: int) -> int:
    """労基法34条が求める最低休憩。"""
    for threshold, required in MIN_BREAK_RULES:
        if worked_minutes > threshold:
            return required
    return 0


def calculate_daily(punch: PunchInput, pattern: WorkPatternSpec) -> DailyCalculation:
    """1日分の打刻から労働時間の内訳を求める。

    丸めは行わない。打刻は1分単位でそのまま扱う（設計書 第5.2章）。
    """
    if punch.clock_out_at <= punch.clock_in_at:
        raise InvalidPunchError("退勤時刻は出勤時刻より後である必要があります。")

    span = _minutes(punch.clock_out_at - punch.clock_in_at)

    if pattern.break_mode is BreakMode.AUTO_DEDUCT:
        break_minutes = resolve_auto_break(span, pattern.break_rules)
        break_night = 0
    else:
        break_minutes = 0
        break_night = 0
        for b_start, b_end in punch.breaks:
            if b_end <= b_start:
                raise InvalidPunchError("休憩の終了時刻は開始時刻より後である必要があります。")
            break_minutes += _overlap_minutes(
                punch.clock_in_at, punch.clock_out_at, b_start, b_end
            )
            break_night += night_overlap_minutes(
                max(b_start, punch.clock_in_at), min(b_end, punch.clock_out_at)
            )

    break_minutes = min(break_minutes, span)
    worked = max(0, span - break_minutes)

    warnings: list[str] = []
    required = required_break_minutes(worked)
    if break_minutes < required:
        warnings.append(
            f"休憩が{required}分に足りていません（労働基準法34条）。現在 {break_minutes}分。"
        )

    night = max(
        0,
        night_overlap_minutes(punch.clock_in_at, punch.clock_out_at) - break_night,
    )

    if punch.day_type is DayType.STATUTORY_HOLIDAY:
        # 法定休日の労働は残業ではなく休日労働として集計する
        holiday_minutes = worked
        within_legal = 0
        statutory = 0
    else:
        holiday_minutes = 0
        within_legal = max(0, min(worked, LEGAL_DAILY_MINUTES) - pattern.scheduled_minutes)
        statutory = max(0, worked - LEGAL_DAILY_MINUTES)

    return DailyCalculation(
        worked_minutes=worked,
        break_minutes=break_minutes,
        overtime_within_legal=within_legal,
        overtime_statutory=statutory,
        night_minutes=night,
        holiday_minutes=holiday_minutes,
        warnings=tuple(warnings),
    )
