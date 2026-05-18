"""
BrainState — persists the Brain's decision log to disk.

Every action the Brain takes is recorded with full context:
  - timestamp, strategy affected, action type
  - before/after values, reasoning, current regime
  - snapshot of performance metrics at decision time

The log is capped at 500 decisions (oldest pruned) to prevent unbounded growth.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class BrainDecision:
    timestamp: str           # ISO-8601 UTC
    strategy_id: str
    action: str              # "set_risk_mode" | "set_param" | "enable_strategy" | "disable_strategy"
    reason: str
    before: dict[str, Any]
    after: dict[str, Any]
    regime: str
    metrics_snapshot: dict[str, Any]


class BrainState:
    _MAX_DECISIONS = 500

    def __init__(self, path: Path) -> None:
        self._path = path
        self._decisions: list[BrainDecision] = []
        self._load()

    def record(self, decision: BrainDecision) -> None:
        self._decisions.append(decision)
        if len(self._decisions) > self._MAX_DECISIONS:
            self._decisions = self._decisions[-self._MAX_DECISIONS:]
        self._save()

    def all_decisions(self) -> list[BrainDecision]:
        return list(self._decisions)

    def recent_decisions(self, n: int = 10) -> list[BrainDecision]:
        return self._decisions[-n:]

    def decisions_for_strategy(self, strategy_id: str) -> list[BrainDecision]:
        return [d for d in self._decisions if d.strategy_id == strategy_id]

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text())
            self._decisions = [BrainDecision(**d) for d in data.get("decisions", [])]
        except Exception:
            self._decisions = []

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps({"decisions": [asdict(d) for d in self._decisions]}, indent=2)
        )

    def to_summary(self) -> dict:
        action_counts: dict[str, int] = {}
        for d in self._decisions:
            action_counts[d.action] = action_counts.get(d.action, 0) + 1
        return {
            "total_decisions": len(self._decisions),
            "action_counts": action_counts,
            "recent": [asdict(d) for d in self._decisions[-3:]],
        }
