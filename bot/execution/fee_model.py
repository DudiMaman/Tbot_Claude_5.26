"""
Fee-aware profitability calculations.
Computes expected R:R AFTER fees and slippage — the core gate for all trades.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from bot.core.config import BrokerConfig


@dataclass
class TradeCost:
    commission_entry: float
    commission_exit: float
    slippage_entry: float
    slippage_exit: float

    @property
    def total(self) -> float:
        return self.commission_entry + self.commission_exit + self.slippage_entry + self.slippage_exit


class FeeModel:
    def __init__(self, broker_config: BrokerConfig) -> None:
        self._cfg = broker_config

    def compute_trade_cost(
        self,
        qty: float,
        entry_price: float,
        exit_price: float,
        order_type: Literal["market", "limit"] = "market",
    ) -> TradeCost:
        fee_rate = (
            self._cfg.fee_schedule.taker
            if order_type == "market"
            else self._cfg.fee_schedule.maker
        )
        slippage_rate = self._cfg.slippage_estimate_bps / 10_000

        notional_entry = qty * entry_price
        notional_exit = qty * exit_price

        return TradeCost(
            commission_entry=notional_entry * fee_rate,
            commission_exit=notional_exit * fee_rate,
            slippage_entry=notional_entry * slippage_rate,
            slippage_exit=notional_exit * slippage_rate,
        )

    def compute_expected_r(
        self,
        entry: float,
        stop_loss: float,
        take_profit: float,
        qty: float,
        side: Literal["long", "short"],
        order_type: Literal["market", "limit"] = "market",
    ) -> float:
        """Return R:R ratio after deducting all fees and slippage on both legs."""
        if qty <= 0 or entry <= 0:
            return 0.0

        cost = self.compute_trade_cost(qty, entry, take_profit, order_type)

        if side == "long":
            gross_reward = (take_profit - entry) * qty
            gross_risk = (entry - stop_loss) * qty
        else:
            gross_reward = (entry - take_profit) * qty
            gross_risk = (stop_loss - entry) * qty

        if gross_risk <= 0:
            return 0.0

        net_reward = gross_reward - cost.total
        net_risk = gross_risk + cost.commission_entry + cost.slippage_entry

        if net_risk <= 0:
            return 0.0

        return net_reward / net_risk

    def annotate_signal(self, signal: "Signal", qty: float) -> None:  # type: ignore[name-defined]
        """Mutate signal in-place with fee_estimate and expected_r_after_fees."""
        from bot.core.events import Signal  # local import to avoid circular

        cost = self.compute_trade_cost(qty, signal.entry_price, signal.take_profit)
        signal.fee_estimate = cost.total
        signal.expected_r_after_fees = self.compute_expected_r(
            signal.entry_price,
            signal.stop_loss,
            signal.take_profit,
            qty,
            "long" if signal.direction == "long" else "short",
        )
