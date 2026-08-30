"""有給の残日数・FIFO消化・失効判定（設計書 第6.2章・第13.1章の境界値）。"""
from datetime import date
from decimal import Decimal

import pytest

from apps.leave.services.balance import (
    CarryoverExpiryAction,
    GrantLot,
    InsufficientBalanceError,
    expiring_lots,
    plan_carryover_expiry,
    plan_consumption,
    remaining_days,
)


def test_remaining_days_sums_active_lots_only():
    lots = (
        GrantLot(id=1, days=Decimal("10"), expires_on=date(2025, 1, 1), consumed=Decimal("3")),
        GrantLot(id=2, days=Decimal("20"), expires_on=date(2026, 12, 31), consumed=Decimal("0")),
    )
    assert remaining_days(lots, as_of=date(2026, 1, 1)) == Decimal("20")


def test_plan_consumption_uses_fifo_by_expiry():
    lots = (
        GrantLot(id=1, days=Decimal("3"), expires_on=date(2026, 3, 31)),
        GrantLot(id=2, days=Decimal("20"), expires_on=date(2027, 3, 31)),
    )
    plan = plan_consumption(lots, Decimal("5"), as_of=date(2026, 1, 1))
    assert plan.allocations == ((1, Decimal("3")), (2, Decimal("2")))
    assert plan.total_days == Decimal("5")


def test_plan_consumption_raises_when_insufficient():
    lots = (GrantLot(id=1, days=Decimal("2"), expires_on=date(2027, 3, 31)),)
    with pytest.raises(InsufficientBalanceError):
        plan_consumption(lots, Decimal("3"), as_of=date(2026, 1, 1))


def test_plan_consumption_rejects_zero_or_negative_days():
    with pytest.raises(ValueError):
        plan_consumption((), Decimal("0"), as_of=date(2026, 1, 1))


def test_carryover_limit_boundary_exactly_used_up():
    """繰越上限ちょうどの日数を申請しても不足にならない境界値。"""
    lots = (GrantLot(id=1, days=Decimal("4"), expires_on=date(2026, 6, 30)),)
    plan = plan_consumption(lots, Decimal("4"), as_of=date(2026, 1, 1))
    assert plan.total_days == Decimal("4")
    assert remaining_days(
        (GrantLot(id=1, days=Decimal("4"), expires_on=date(2026, 6, 30), consumed=Decimal("4")),),
        as_of=date(2026, 1, 1),
    ) == Decimal("0")


def test_grant_and_expiry_on_same_day_is_still_active():
    """付与日と失効日が同日（＝失効年数0相当）でも、その日はまだ有効として扱う。"""
    lots = (GrantLot(id=1, days=Decimal("5"), expires_on=date(2026, 1, 1)),)
    assert remaining_days(lots, as_of=date(2026, 1, 1)) == Decimal("5")
    assert remaining_days(lots, as_of=date(2026, 1, 2)) == Decimal("0")


def test_expiring_lots_only_include_ones_with_remaining_balance():
    lots = (
        GrantLot(id=1, days=Decimal("5"), expires_on=date(2025, 12, 31), consumed=Decimal("5")),
        GrantLot(id=2, days=Decimal("5"), expires_on=date(2025, 12, 31), consumed=Decimal("2")),
    )
    expired = expiring_lots(lots, as_of=date(2026, 1, 1))
    assert [lot.id for lot in expired] == [2]


def test_carryover_expiry_none_limit_is_unlimited():
    lots = (GrantLot(id=1, days=Decimal("100"), expires_on=date(2027, 1, 1)),)
    assert plan_carryover_expiry(lots, as_of=date(2026, 1, 1), carryover_limit_days=None) == ()


def test_carryover_expiry_exactly_at_limit_does_not_expire():
    """繰越上限ちょうどは超過とみなさない境界値。"""
    lots = (GrantLot(id=1, days=Decimal("10"), expires_on=date(2027, 1, 1)),)
    assert plan_carryover_expiry(lots, as_of=date(2026, 1, 1), carryover_limit_days=Decimal("10")) == ()


def test_carryover_expiry_just_over_limit_expires_the_excess_only():
    lots = (GrantLot(id=1, days=Decimal("10.5"), expires_on=date(2027, 1, 1)),)
    actions = plan_carryover_expiry(lots, as_of=date(2026, 1, 1), carryover_limit_days=Decimal("10"))
    assert actions == (CarryoverExpiryAction(1, Decimal("0.5")),)


def test_carryover_expiry_takes_from_nearest_expiry_first_across_multiple_lots():
    lots = (
        GrantLot(id=1, days=Decimal("5"), expires_on=date(2026, 6, 30)),
        GrantLot(id=2, days=Decimal("10"), expires_on=date(2027, 6, 30)),
    )
    # 合計15日のうち上限8日を超える7日分を、失効が近いロット(1)から優先的に失効させる
    actions = plan_carryover_expiry(lots, as_of=date(2026, 1, 1), carryover_limit_days=Decimal("8"))
    assert actions[0].grant_id == 1
    assert actions[0].days == Decimal("5")
    assert actions[1].grant_id == 2
    assert actions[1].days == Decimal("2")


def test_carryover_expiry_ignores_already_expired_lots():
    lots = (GrantLot(id=1, days=Decimal("20"), expires_on=date(2025, 1, 1)),)  # as_of より前に失効済み
    assert plan_carryover_expiry(lots, as_of=date(2026, 1, 1), carryover_limit_days=Decimal("5")) == ()
