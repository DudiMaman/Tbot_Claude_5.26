from abc import ABC, abstractmethod
from datetime import datetime, timezone


class Clock(ABC):
    @abstractmethod
    def now(self) -> datetime:
        ...


class WallClock(Clock):
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class SimulatedClock(Clock):
    def __init__(self, start: datetime) -> None:
        self._current = start

    def now(self) -> datetime:
        return self._current

    def advance(self, dt: datetime) -> None:
        self._current = dt
