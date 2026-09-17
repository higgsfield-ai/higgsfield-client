import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class SessionStatus(str, Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    AWAITING_INPUT = "awaiting_input"
    TERMINATED = "terminated"


class MessageStatus(str, Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


_URL_RE = re.compile(r"https?://[^\s)\]>\"']+")


@dataclass
class AgentMessage:
    """One row of the session transcript (user or assistant)."""

    message_id: str
    role: str
    status: str
    message: Any
    created_at: str
    # Actual LLM cost of the turn in USD (user rows; None = flat charge).
    llm_cost_usd: Optional[str] = None

    @property
    def text(self) -> str:
        """Plain text of the message.

        User rows carry ``{"type": "text", "text": ...}``; assistant rows carry
        a structured message whose ``parts`` list holds the answer as blocks
        with ``type == "text"`` (other part types are agent internals).
        """
        body = self.message
        if not isinstance(body, dict):
            return ""
        if isinstance(body.get("text"), str):
            return body["text"]
        parts = body.get("parts")
        if not isinstance(parts, list):
            return ""
        return "\n".join(
            p["text"]
            for p in parts
            if isinstance(p, dict)
            and p.get("type") == "text"
            and isinstance(p.get("text"), str)
        )

    @property
    def asset_urls(self) -> List[str]:
        """URLs the agent included in its answer (generated assets, uploads)."""
        seen: Dict[str, None] = {}
        for url in _URL_RE.findall(self.text):
            seen.setdefault(url.rstrip(".,;"))
        return list(seen)

    @property
    def is_terminal(self) -> bool:
        return self.status in (MessageStatus.COMPLETED, MessageStatus.FAILED)


@dataclass
class SessionState:
    """The poll response: session status plus the transcript slice."""

    status: SessionStatus
    messages: List[AgentMessage] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionState":
        return cls(
            status=SessionStatus(data.get("status", "idle")),
            messages=[
                AgentMessage(
                    message_id=m["message_id"],
                    role=m["role"],
                    status=m["status"],
                    message=m.get("message"),
                    created_at=m.get("created_at", ""),
                    llm_cost_usd=m.get("llm_cost_usd"),
                )
                for m in data.get("messages", [])
            ],
        )


@dataclass
class TurnResult:
    """Outcome of one ``run()`` turn."""

    status: str  # "completed" | "failed" | "awaiting_input"
    message: Optional[AgentMessage]

    @property
    def text(self) -> str:
        return self.message.text if self.message else ""

    @property
    def asset_urls(self) -> List[str]:
        return self.message.asset_urls if self.message else []

    def __str__(self) -> str:
        return f"<TurnResult {self.status}>"


@dataclass
class AgentSession:
    """Handle for one agent session (id + status snapshot)."""

    session_id: str
    status: SessionStatus

    def __str__(self) -> str:
        return f"<AgentSession {self.session_id}, {self.status.value}>"
