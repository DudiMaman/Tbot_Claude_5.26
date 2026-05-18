"""Fixed-fractional position sizer with min-notional enforcement."""
from __future__ import annotations

import math

from bot.core.config import BrokerConfig, RiskConfig
from bot.core.events import Signal
from bot.core.modes import RiskMode


class PositionSizer:
    def __init__(self, risk_config: RiskConfig, broker_config: BrokerConfig) -> None:
        self._rcfg = risk_config
        self._bcfg = broker_config

    def compute_qty(
        self,
        signal: Signal,
        capital: float,
        risk_mode: RiskMode = RiskMode.NORMAL,
        step_size: float = 0.0001,    # exchange lot step; override per symbol
        available_cash: float | None = None,
    ) -> tuple[float, str]:
        """
        Returns (qty, rejection_reason). rejection_reason is empty string on success.
        available_cash: actual spendable cash (may differ from capital which includes unrealized P&L).
        """
        if signal.entry_price <= 0 or signal.stop_loss <= 0:
            return 0.0, "invalid_prices"

        risk_dollars = capital * self._rcfg.risk_per_trade_pct * risk_mode.sizing_multiplier()
        risk_per_unit = abs(signal.entry_price - signal.stop_loss)

        if risk_per_unit == 0:
            return 0.0, "zero_risk_per_unit"

        raw_qty = risk_dollars / risk_per_unit

        # Round down to exchange step size
        qty = math.floor(raw_qty / step_size) * step_size
        qty = round(qty, 8)

        # Cap position size by available cash (95% to reserve for fees/slippage)
        cash_budget = available_cash if available_cash is not None else capital
        max_qty_from_cash = math.floor((cash_budget * 0.95) / signal.entry_price / step_size) * step_size
        max_qty_from_cash = round(max_qty_from_cash, 8)
        if qty > max_qty_from_cash:
            qty = max_qty_from_cash

        notional = qty * signal.entry_price
        min_notional = self._bcfg.min_notional_usd

        if notional < min_notional:
            # Attempt to size UP to meet min notional, capped at 1.5× risk limit
            min_qty = math.ceil(min_notional / signal.entry_price / step_size) * step_size
            min_qty_risk = abs(signal.entry_price - signal.stop_loss) * min_qty
            max_allowed_risk = capital * self._rcfg.risk_per_trade_pct * 1.5

            if min_qty_risk <= max_allowed_risk:
                qty = min_qty
            else:
                return 0.0, "min_notional_unachievable"

        if qty <= 0:
            return 0.0, "zero_qty"

        return qty, ""
