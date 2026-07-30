from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class RegimePillar:
    name: str
    score: float
    state: str
    details: str
    available_inputs: int = 0
    expected_inputs: int = 0

    @property
    def coverage(self) -> float:
        if self.expected_inputs <= 0:
            return 1.0
        return min(1.0, self.available_inputs / self.expected_inputs)


@dataclass(frozen=True)
class RegimeLayer:
    key: str
    title: str
    horizon: str
    diagnosis: str
    score: float
    previous_diagnosis: str
    previous_score: float
    pillars: List[RegimePillar]

    @property
    def transition(self) -> str:
        return f"{self.previous_diagnosis} → {self.diagnosis}"

    @property
    def coverage(self) -> float:
        expected = sum(p.expected_inputs for p in self.pillars)
        available = sum(p.available_inputs for p in self.pillars)
        return available / expected if expected else 1.0
