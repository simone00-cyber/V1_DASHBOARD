from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4


MessageRole = Literal["user", "assistant", "system"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class ConversationMessage:
    role: MessageRole
    content: str
    created_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.content = self.content.strip()

        if not self.content:
            raise ValueError("Conversation message content cannot be empty.")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "ConversationMessage":
        role = str(data.get("role", "")).strip()

        if role not in {"user", "assistant", "system"}:
            raise ValueError(f"Unsupported conversation role: {role!r}")

        metadata = data.get("metadata", {})

        if not isinstance(metadata, dict):
            metadata = {}

        return cls(
            role=role,  # type: ignore[arg-type]
            content=str(data.get("content", "")),
            created_at=str(data.get("created_at") or utc_now_iso()),
            metadata=metadata,
        )


@dataclass
class Conversation:
    id: str = field(default_factory=lambda: str(uuid4()))
    title: str = "New research conversation"
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    messages: list[ConversationMessage] = field(default_factory=list)

    def add_message(
        self,
        role: MessageRole,
        content: str,
        metadata: dict[str, object] | None = None,
    ) -> ConversationMessage:
        message = ConversationMessage(
            role=role,
            content=content,
            metadata=metadata or {},
        )

        self.messages.append(message)
        self.updated_at = utc_now_iso()

        if self.title == "New research conversation" and role == "user":
            self.title = self._build_title(content)

        return message

    def add_user_message(
        self,
        content: str,
        metadata: dict[str, object] | None = None,
    ) -> ConversationMessage:
        return self.add_message(
            role="user",
            content=content,
            metadata=metadata,
        )

    def add_assistant_message(
        self,
        content: str,
        metadata: dict[str, object] | None = None,
    ) -> ConversationMessage:
        return self.add_message(
            role="assistant",
            content=content,
            metadata=metadata,
        )

    def add_system_message(
        self,
        content: str,
        metadata: dict[str, object] | None = None,
    ) -> ConversationMessage:
        return self.add_message(
            role="system",
            content=content,
            metadata=metadata,
        )

    def history(
        self,
        include_system: bool = True,
    ) -> list[dict[str, object]]:
        if include_system:
            messages = self.messages
        else:
            messages = [
                message
                for message in self.messages
                if message.role != "system"
            ]

        return [message.to_dict() for message in messages]

    def last_message(
        self,
        role: MessageRole | None = None,
    ) -> ConversationMessage | None:
        if role is None:
            return self.messages[-1] if self.messages else None

        for message in reversed(self.messages):
            if message.role == role:
                return message

        return None

    def clear(self, preserve_system_messages: bool = False) -> None:
        if preserve_system_messages:
            self.messages = [
                message
                for message in self.messages
                if message.role == "system"
            ]
        else:
            self.messages.clear()

        self.updated_at = utc_now_iso()

    def is_empty(self) -> bool:
        return not self.messages

    def message_count(self, role: MessageRole | None = None) -> int:
        if role is None:
            return len(self.messages)

        return sum(
            1
            for message in self.messages
            if message.role == role
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "messages": [
                message.to_dict()
                for message in self.messages
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "Conversation":
        raw_messages = data.get("messages", [])

        if not isinstance(raw_messages, list):
            raise ValueError("Conversation messages must be a list.")

        messages = [
            ConversationMessage.from_dict(message)
            for message in raw_messages
            if isinstance(message, dict)
        ]

        return cls(
            id=str(data.get("id") or uuid4()),
            title=str(data.get("title") or "New research conversation"),
            created_at=str(data.get("created_at") or utc_now_iso()),
            updated_at=str(data.get("updated_at") or utc_now_iso()),
            messages=messages,
        )

    @staticmethod
    def _build_title(content: str, max_length: int = 60) -> str:
        normalized = " ".join(content.strip().split())

        if len(normalized) <= max_length:
            return normalized

        return f"{normalized[: max_length - 1].rstrip()}…"