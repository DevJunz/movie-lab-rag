"""실제로 기다리지 않는 시계. `sleep`은 시간을 앞으로 보내고 기다린 값을 기록한다."""

from __future__ import annotations


class FakeClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.now = start
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += max(seconds, 0.0)

    def advance(self, seconds: float) -> None:
        self.now += seconds
