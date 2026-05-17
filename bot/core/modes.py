from enum import Enum


class ExecutionMode(str, Enum):
    BACKTEST = "backtest"
    PAPER = "paper"
    LIVE = "live"


class RiskMode(str, Enum):
    DEFENSIVE = "defensive"
    NORMAL = "normal"
    AGGRESSIVE = "aggressive"

    def sizing_multiplier(self) -> float:
        return {
            RiskMode.DEFENSIVE: 0.5,
            RiskMode.NORMAL: 1.0,
            RiskMode.AGGRESSIVE: 1.25,
        }[self]
