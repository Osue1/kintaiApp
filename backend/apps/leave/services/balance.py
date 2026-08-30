"""有給の残日数計算・FIFO消化・失効判定を行う純関数。

残日数はカラムで持たず、付与ロット（PaidLeaveGrant）と消化明細（LeaveConsumption）から
常に計算する（設計書 第6.2章 ②「有給は残日数ではなく付与ロットで持つ」）。
ここに Django のモデルは持ち込まない。ビュー側で ORM ↔ この値オブジェクトを変換する。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class GrantLot:
    id: int
    days: Decimal
    expires_on: date
    consumed: Decimal = Decimal("0")

    @property
    def remaining(self) -> Decimal:
        return self.days - self.consumed


@dataclass(frozen=True, slots=True)
class ConsumptionPlan:
    """FIFO で払い出す消化の内訳。(grant_id, 消化日数) のタプル列。"""

    allocations: tuple[tuple[int, Decimal], ...]

    @property
    def total_days(self) -> Decimal:
        total = Decimal("0")
        for _, d in self.allocations:
            total += d
        return total


class InsufficientBalanceError(ValueError):
    """残日数が申請日数に満たない。"""


def active_lots(lots: tuple[GrantLot, ...], as_of: date) -> tuple[GrantLot, ...]:
    """as_of 時点でまだ失効しておらず残日数のあるロットを、失効日が近い順に返す。"""
    return tuple(
        sorted(
            (lot for lot in lots if lot.expires_on >= as_of and lot.remaining > 0),
            key=lambda lot: lot.expires_on,
        )
    )


def remaining_days(lots: tuple[GrantLot, ...], as_of: date) -> Decimal:
    total = Decimal("0")
    for lot in active_lots(lots, as_of):
        total += lot.remaining
    return total


def plan_consumption(lots: tuple[GrantLot, ...], days: Decimal, as_of: date) -> ConsumptionPlan:
    """失効日が近いロットから先入先出（FIFO）で消化計画を立てる。"""
    if days <= 0:
        raise ValueError("消化日数は正の値である必要があります。")
    remaining_to_consume = days
    allocations: list[tuple[int, Decimal]] = []
    for lot in active_lots(lots, as_of):
        if remaining_to_consume <= 0:
            break
        take = min(lot.remaining, remaining_to_consume)
        if take > 0:
            allocations.append((lot.id, take))
            remaining_to_consume -= take
    if remaining_to_consume > 0:
        raise InsufficientBalanceError(f"残日数が不足しています（不足 {remaining_to_consume}日）。")
    return ConsumptionPlan(tuple(allocations))


def expiring_lots(lots: tuple[GrantLot, ...], as_of: date) -> tuple[GrantLot, ...]:
    """as_of より前に失効した、まだ残日数の残っているロット（失効処理の対象）。"""
    return tuple(lot for lot in lots if lot.expires_on < as_of and lot.remaining > 0)


@dataclass(frozen=True, slots=True)
class CarryoverExpiryAction:
    """繰越上限超過による強制失効1件。(対象ロットID, 失効させる日数)。"""

    grant_id: int
    days: Decimal


def plan_carryover_expiry(
    prior_lots: tuple[GrantLot, ...], as_of: date, carryover_limit_days: Decimal | None
) -> tuple[CarryoverExpiryAction, ...]:
    """新しい付与が発生する日に、それ以前からの繰越分（prior_lots の残日数合計）が
    carryover_limit_days を超えていたら、失効日が近いロットから順に超過分を失効させる
    （設計書 第6.2章「繰越上限を超える分は次回付与日に失効処理」）。

    carryover_limit_days が None のときは無制限として何もしない。ちょうど上限と一致する
    場合は超過とみなさない（境界値は失効させない）。
    """
    if carryover_limit_days is None:
        return ()
    total = remaining_days(prior_lots, as_of)
    excess = total - carryover_limit_days
    if excess <= 0:
        return ()

    actions: list[CarryoverExpiryAction] = []
    remaining_to_expire = excess
    for lot in active_lots(prior_lots, as_of):
        if remaining_to_expire <= 0:
            break
        take = min(lot.remaining, remaining_to_expire)
        if take > 0:
            actions.append(CarryoverExpiryAction(lot.id, take))
            remaining_to_expire -= take
    return tuple(actions)
