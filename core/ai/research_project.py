from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from core.ai.conversation import Conversation


ProjectStatus = Literal[
    "draft",
    "strategy_incomplete",
    "ready_for_review",
    "approved",
    "archived",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_strategy_definition() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "instrument": {
            "ticker": "",
            "timeframe": "1d",
            "start_date": None,
            "end_date": None,
            "benchmark": None,
        },
        "direction": {
            "long_enabled": True,
            "short_enabled": False,
        },
        "entry": {
            "long": [],
            "short": [],
        },
        "exit": {
            "long": [],
            "short": [],
        },
        "risk": {
            "initial_capital": 100_000.0,
            "position_sizing_method": "percentage_of_equity",
            "position_size": 100.0,
            "risk_per_trade": None,
            "stop_loss": None,
            "take_profit": None,
            "trailing_stop": None,
            "maximum_holding_bars": None,
            "maximum_open_positions": 1,
        },
        "execution": {
            "order_type": "market",
            "signal_execution": "next_bar_open",
            "commission_type": "percentage",
            "commission_value": 0.0,
            "slippage_type": "percentage",
            "slippage_value": 0.0,
            "spread": 0.0,
        },
        "metadata": {
            "name": "",
            "description": "",
            "strategy_type": None,
            "tags": [],
        },
    }


@dataclass(slots=True)
class ProjectNote:
    content: str
    created_at: str = field(default_factory=utc_now_iso)
    author: str = "user"

    def __post_init__(self) -> None:
        self.content = self.content.strip()

        if not self.content:
            raise ValueError("Project note content cannot be empty.")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectNote":
        return cls(
            content=str(data.get("content", "")),
            created_at=str(data.get("created_at") or utc_now_iso()),
            author=str(data.get("author") or "user"),
        )


@dataclass
class ResearchProject:
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = "Untitled Research Project"
    description: str = ""
    status: ProjectStatus = "draft"
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    conversation: Conversation = field(default_factory=Conversation)
    strategy: dict[str, Any] = field(default_factory=default_strategy_definition)

    notes: list[ProjectNote] = field(default_factory=list)
    strategy_version: int = 1
    approved_strategy_version: int | None = None

    backtest_ids: list[str] = field(default_factory=list)
    optimization_ids: list[str] = field(default_factory=list)
    monte_carlo_ids: list[str] = field(default_factory=list)
    walk_forward_ids: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.name = self.name.strip() or "Untitled Research Project"
        self.description = self.description.strip()

        if self.status not in {
            "draft",
            "strategy_incomplete",
            "ready_for_review",
            "approved",
            "archived",
        }:
            raise ValueError(f"Unsupported project status: {self.status!r}")

        if self.strategy_version < 1:
            raise ValueError("Strategy version must be at least 1.")

        self._ensure_strategy_structure()

    @property
    def ticker(self) -> str:
        instrument = self.strategy.get("instrument", {})
        return str(instrument.get("ticker", "")).strip().upper()

    @property
    def timeframe(self) -> str:
        instrument = self.strategy.get("instrument", {})
        return str(instrument.get("timeframe", "1d")).strip()

    @property
    def is_approved(self) -> bool:
        return (
            self.status == "approved"
            and self.approved_strategy_version == self.strategy_version
        )

    def set_ticker(self, ticker: str) -> None:
        normalized = ticker.strip().upper()

        if not normalized:
            raise ValueError("Ticker cannot be empty.")

        self.strategy["instrument"]["ticker"] = normalized
        self.mark_strategy_changed()

        if self.name == "Untitled Research Project":
            self.name = f"{normalized} Research Project"

    def set_timeframe(self, timeframe: str) -> None:
        normalized = timeframe.strip().lower()

        allowed = {
            "1m",
            "2m",
            "5m",
            "15m",
            "30m",
            "60m",
            "90m",
            "1h",
            "4h",
            "1d",
            "5d",
            "1wk",
            "1mo",
            "3mo",
        }

        if normalized not in allowed:
            raise ValueError(f"Unsupported timeframe: {timeframe!r}")

        self.strategy["instrument"]["timeframe"] = normalized
        self.mark_strategy_changed()

    def update_strategy_section(
        self,
        section: str,
        value: dict[str, Any],
    ) -> None:
        allowed_sections = {
            "instrument",
            "direction",
            "entry",
            "exit",
            "risk",
            "execution",
            "metadata",
        }

        if section not in allowed_sections:
            raise ValueError(f"Unsupported strategy section: {section!r}")

        if not isinstance(value, dict):
            raise TypeError("Strategy section value must be a dictionary.")

        self.strategy[section] = value
        self.mark_strategy_changed()

    def mark_strategy_changed(self) -> None:
        self.strategy_version += 1
        self.approved_strategy_version = None
        self.status = "strategy_incomplete"
        self.touch()

    def mark_ready_for_review(self) -> None:
        self.status = "ready_for_review"
        self.touch()

    def approve_strategy(self) -> None:
        if not self.ticker:
            raise ValueError("The strategy cannot be approved without a ticker.")

        self.status = "approved"
        self.approved_strategy_version = self.strategy_version
        self.touch()

    def revoke_approval(self) -> None:
        self.approved_strategy_version = None
        self.status = "strategy_incomplete"
        self.touch()

    def archive(self) -> None:
        self.status = "archived"
        self.touch()

    def add_note(
        self,
        content: str,
        author: str = "user",
    ) -> ProjectNote:
        note = ProjectNote(
            content=content,
            author=author,
        )

        self.notes.append(note)
        self.touch()
        return note

    def register_backtest(self, backtest_id: str) -> None:
        self._register_result_id(self.backtest_ids, backtest_id)

    def register_optimization(self, optimization_id: str) -> None:
        self._register_result_id(self.optimization_ids, optimization_id)

    def register_monte_carlo(self, monte_carlo_id: str) -> None:
        self._register_result_id(self.monte_carlo_ids, monte_carlo_id)

    def register_walk_forward(self, walk_forward_id: str) -> None:
        self._register_result_id(self.walk_forward_ids, walk_forward_id)

    def touch(self) -> None:
        self.updated_at = utc_now_iso()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "conversation": self.conversation.to_dict(),
            "strategy": self.strategy,
            "notes": [note.to_dict() for note in self.notes],
            "strategy_version": self.strategy_version,
            "approved_strategy_version": self.approved_strategy_version,
            "backtest_ids": list(self.backtest_ids),
            "optimization_ids": list(self.optimization_ids),
            "monte_carlo_ids": list(self.monte_carlo_ids),
            "walk_forward_ids": list(self.walk_forward_ids),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResearchProject":
        raw_conversation = data.get("conversation", {})
        raw_strategy = data.get("strategy", {})
        raw_notes = data.get("notes", [])

        if not isinstance(raw_conversation, dict):
            raise ValueError("Project conversation must be a dictionary.")

        if not isinstance(raw_strategy, dict):
            raise ValueError("Project strategy must be a dictionary.")

        if not isinstance(raw_notes, list):
            raise ValueError("Project notes must be a list.")

        return cls(
            id=str(data.get("id") or uuid4()),
            name=str(data.get("name") or "Untitled Research Project"),
            description=str(data.get("description") or ""),
            status=str(data.get("status") or "draft"),  # type: ignore[arg-type]
            created_at=str(data.get("created_at") or utc_now_iso()),
            updated_at=str(data.get("updated_at") or utc_now_iso()),
            conversation=Conversation.from_dict(raw_conversation),
            strategy=raw_strategy or default_strategy_definition(),
            notes=[
                ProjectNote.from_dict(note)
                for note in raw_notes
                if isinstance(note, dict)
            ],
            strategy_version=int(data.get("strategy_version") or 1),
            approved_strategy_version=(
                int(data["approved_strategy_version"])
                if data.get("approved_strategy_version") is not None
                else None
            ),
            backtest_ids=[
                str(value)
                for value in data.get("backtest_ids", [])
            ],
            optimization_ids=[
                str(value)
                for value in data.get("optimization_ids", [])
            ],
            monte_carlo_ids=[
                str(value)
                for value in data.get("monte_carlo_ids", [])
            ],
            walk_forward_ids=[
                str(value)
                for value in data.get("walk_forward_ids", [])
            ],
        )

    def _ensure_strategy_structure(self) -> None:
        default = default_strategy_definition()

        for key, default_value in default.items():
            if key not in self.strategy:
                self.strategy[key] = default_value

        for nested_section in {
            "instrument",
            "direction",
            "entry",
            "exit",
            "risk",
            "execution",
            "metadata",
        }:
            if not isinstance(self.strategy[nested_section], dict):
                raise ValueError(
                    f"Strategy section {nested_section!r} must be a dictionary."
                )

    def _register_result_id(
        self,
        target: list[str],
        result_id: str,
    ) -> None:
        normalized = result_id.strip()

        if not normalized:
            raise ValueError("Result identifier cannot be empty.")

        if normalized not in target:
            target.append(normalized)
            self.touch()