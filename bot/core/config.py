"""Global configuration loading with Pydantic v2 validation."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal, Optional

import yaml
from pydantic import BaseModel, Field
from pydantic import model_validator


class RiskConfig(BaseModel):
    capital_usd: float = Field(gt=0)
    risk_per_trade_pct: float = Field(gt=0, le=0.05, default=0.01)
    max_daily_loss_pct: float = Field(gt=0, le=0.10, default=0.03)
    max_open_positions: int = Field(ge=1, le=20, default=5)
    min_r_after_fees: float = Field(ge=1.0, default=1.5)
    risk_mode: Literal["defensive", "normal", "aggressive"] = "normal"
    execution_mode: Literal["backtest", "paper", "live"] = "paper"
    losing_streak_defensive: int = Field(ge=1, default=5)
    losing_streak_halt: int = Field(ge=1, default=10)
    losing_streak_halt_reset_bars: int = Field(ge=0, default=50)
    max_crypto_exposure_pct: float = Field(gt=0, le=1.0, default=0.60)
    max_stock_exposure_pct: float = Field(gt=0, le=1.0, default=0.40)
    stale_order_timeout_minutes: int = Field(ge=1, default=30)

    @model_validator(mode="after")
    def halt_gt_defensive(self) -> "RiskConfig":
        if self.losing_streak_halt <= self.losing_streak_defensive:
            raise ValueError("losing_streak_halt must be > losing_streak_defensive")
        return self


class BrokerFeeSchedule(BaseModel):
    maker: float = 0.001
    taker: float = 0.001
    commission_per_trade: float = 0.0
    sec_fee_per_dollar: float = 0.0


class BrokerConfig(BaseModel):
    name: str
    asset_class: str
    fee_schedule: BrokerFeeSchedule
    slippage_estimate_bps: float = 5.0
    min_notional_usd: float = 10.0
    rest_weight_limit_per_minute: int = 1200
    rest_weight_backoff_threshold: float = 0.80
    default_symbols: list[str] = Field(default_factory=list)
    # Allow arbitrary extra fields (e.g., rest_url, testnet_rest_url)
    model_config = {"extra": "allow"}


class StrategyConfig(BaseModel):
    strategy_id: str
    strategy_class: str
    symbols: list[str]
    timeframes: dict[str, str]
    warmup_bars: int = Field(ge=1, default=50)
    take_profit_r: float = Field(ge=1.0, default=2.0)
    trailing_stop_pct: Optional[float] = None
    model_config = {"extra": "allow"}


def _load_yaml(path: Path) -> dict[str, Any]:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _env_override(data: dict[str, Any]) -> dict[str, Any]:
    """Apply environment variable overrides (uppercase key names)."""
    overrides = {
        "capital_usd": os.environ.get("CAPITAL_USD"),
        "risk_mode": os.environ.get("RISK_MODE"),
        "execution_mode": os.environ.get("EXECUTION_MODE"),
    }
    for key, val in overrides.items():
        if val is not None:
            data[key] = val
    return data


def load_risk_config(config_dir: Path | str = "config") -> RiskConfig:
    config_dir = Path(config_dir)
    data = _load_yaml(config_dir / "base.yaml")
    data = _env_override(data)
    return RiskConfig(**data)


def load_broker_config(name: str, config_dir: Path | str = "config") -> BrokerConfig:
    config_dir = Path(config_dir)
    data = _load_yaml(config_dir / "brokers" / f"{name}.yaml")
    return BrokerConfig(**data)


def load_strategy_config(name: str, config_dir: Path | str = "config") -> StrategyConfig:
    config_dir = Path(config_dir)
    data = _load_yaml(config_dir / "strategies" / f"{name}.yaml")
    return StrategyConfig(**data)
