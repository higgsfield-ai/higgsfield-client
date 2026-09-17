"""Agent API resources: ``client.agents.sessions`` / ``client.agents.media``.

Agent resources share the SDK client authentication, base URL, and timeout.
Presigned uploads use the separate unauthenticated upload client.
"""

import asyncio
import time
from typing import Any, Callable, Dict, Optional

import httpx

from higgsfield_client.agents.errors import (
    AgentError,
    AgentTimeoutError,
    raise_for_agent_status,
)
from higgsfield_client.agents.types import (
    AgentSession,
    SessionState,
    SessionStatus,
    TurnResult,
)

_POLL_INITIAL = 2.0
_POLL_MAX = 10.0
_POLL_BACKOFF = 1.5
_DEFAULT_TURN_TIMEOUT = 1800.0

# A question handler gets the agent's question text and returns the answer.
QuestionHandler = Callable[[str], str]


def _turn_outcome(state: SessionState) -> Optional[TurnResult]:
    """Decide whether the current turn is done.

    The poll uses ``after=<user message id>``, so every assistant row in the
    slice belongs to this turn (or its resume). Terminal assistant row wins;
    a parked session (``awaiting_input``) surfaces the question instead.
    """
    assistants = [m for m in state.messages if m.role == "assistant"]
    for m in reversed(assistants):
        if m.is_terminal:
            return TurnResult(status=m.status, message=m)
    if state.status == SessionStatus.AWAITING_INPUT:
        parked = assistants[-1] if assistants else None
        return TurnResult(status="awaiting_input", message=parked)
    return None


class Sessions:
    def __init__(self, client: httpx.Client, base_url: str) -> None:
        self._client = client
        self._base = base_url.rstrip("/")

    def _url(self, path: str) -> str:
        return f"{self._base}/v1/agent{path}"

    def create(self, config: Optional[Dict[str, Any]] = None) -> AgentSession:
        resp = self._client.post(self._url("/sessions"), json={"config": config or {}})
        raise_for_agent_status(resp)
        data = resp.json()
        return AgentSession(
            session_id=data["session_id"], status=SessionStatus(data["status"])
        )

    def send(self, session_id: str, content: str) -> str:
        """Submit one message; returns its message_id (turn runs async)."""
        resp = self._client.post(
            self._url(f"/sessions/{session_id}/messages"),
            json={"content": content},
        )
        raise_for_agent_status(resp)
        return resp.json()["message_id"]

    def messages(self, session_id: str, after: Optional[str] = None) -> SessionState:
        params = {"after": after} if after else None
        resp = self._client.get(
            self._url(f"/sessions/{session_id}/messages"), params=params
        )
        raise_for_agent_status(resp)
        return SessionState.from_dict(resp.json())

    def interrupt(self, session_id: str) -> None:
        resp = self._client.post(self._url(f"/sessions/{session_id}/interrupt"))
        raise_for_agent_status(resp)

    def run(
        self,
        session_id: str,
        content: str,
        on_question: Optional[QuestionHandler] = None,
        timeout: float = _DEFAULT_TURN_TIMEOUT,
    ) -> TurnResult:
        """Send a message and poll until the turn ends.

        Polls with backoff (2s -> 10s). If the agent asks a question and
        ``on_question`` is given, the answer is sent and polling continues;
        without a handler the question comes back as
        ``TurnResult(status="awaiting_input")``.
        """
        deadline = time.monotonic() + timeout
        message_id = self.send(session_id, content)
        delay = _POLL_INITIAL
        while True:
            if time.monotonic() > deadline:
                raise AgentTimeoutError(
                    f"turn did not finish within {timeout:.0f}s "
                    f"(session {session_id}); it keeps running server-side"
                )
            time.sleep(min(delay, max(0.0, deadline - time.monotonic())))
            delay = min(delay * _POLL_BACKOFF, _POLL_MAX)

            state = self.messages(session_id, after=message_id)
            outcome = _turn_outcome(state)
            if outcome is None:
                continue
            if outcome.status == "awaiting_input" and on_question is not None:
                answer = on_question(outcome.text)
                message_id = self.send(session_id, answer)
                delay = _POLL_INITIAL
                continue
            return outcome


class Media:
    def __init__(
        self, client: httpx.Client, upload_client: httpx.Client, base_url: str
    ) -> None:
        self._client = client
        self._upload_client = upload_client
        self._base = base_url.rstrip("/")

    def upload(self, data: bytes, extension: str, type: str = "image") -> str:
        """Upload input bytes for the agent; returns the CDN URL to reference
        in message content. ``type``: image | video | audio | file."""
        resp = self._client.post(
            f"{self._base}/v1/agent/media",
            json={"extension": extension, "type": type},
        )
        raise_for_agent_status(resp)
        slot = resp.json()
        put = self._upload_client.put(
            slot["upload_url"],
            content=data,
            headers={"Content-Type": slot["content_type"]},
            timeout=self._client.timeout,
        )
        put.raise_for_status()
        confirm = self._client.post(
            f"{self._base}/v1/agent/media/{slot['id']}/confirm",
            json={"type": type},
        )
        raise_for_agent_status(confirm)
        if confirm.json().get("status") != "uploaded":
            raise AgentError("Agent media upload has not been confirmed by the server")
        return slot["url"]


class AgentsResource:
    """``client.agents`` — sync Agent API namespace."""

    def __init__(
        self, client: httpx.Client, upload_client: httpx.Client, base_url: str
    ) -> None:
        self.sessions = Sessions(client, base_url)
        self.media = Media(client, upload_client, base_url)


class AsyncSessions:
    def __init__(self, client: httpx.AsyncClient, base_url: str) -> None:
        self._client = client
        self._base = base_url.rstrip("/")

    def _url(self, path: str) -> str:
        return f"{self._base}/v1/agent{path}"

    async def create(self, config: Optional[Dict[str, Any]] = None) -> AgentSession:
        resp = await self._client.post(
            self._url("/sessions"), json={"config": config or {}}
        )
        raise_for_agent_status(resp)
        data = resp.json()
        return AgentSession(
            session_id=data["session_id"], status=SessionStatus(data["status"])
        )

    async def send(self, session_id: str, content: str) -> str:
        resp = await self._client.post(
            self._url(f"/sessions/{session_id}/messages"),
            json={"content": content},
        )
        raise_for_agent_status(resp)
        return resp.json()["message_id"]

    async def messages(
        self, session_id: str, after: Optional[str] = None
    ) -> SessionState:
        params = {"after": after} if after else None
        resp = await self._client.get(
            self._url(f"/sessions/{session_id}/messages"), params=params
        )
        raise_for_agent_status(resp)
        return SessionState.from_dict(resp.json())

    async def interrupt(self, session_id: str) -> None:
        resp = await self._client.post(self._url(f"/sessions/{session_id}/interrupt"))
        raise_for_agent_status(resp)

    async def run(
        self,
        session_id: str,
        content: str,
        on_question: Optional[QuestionHandler] = None,
        timeout: float = _DEFAULT_TURN_TIMEOUT,
    ) -> TurnResult:
        deadline = time.monotonic() + timeout
        message_id = await self.send(session_id, content)
        delay = _POLL_INITIAL
        while True:
            if time.monotonic() > deadline:
                raise AgentTimeoutError(
                    f"turn did not finish within {timeout:.0f}s "
                    f"(session {session_id}); it keeps running server-side"
                )
            await asyncio.sleep(min(delay, max(0.0, deadline - time.monotonic())))
            delay = min(delay * _POLL_BACKOFF, _POLL_MAX)

            state = await self.messages(session_id, after=message_id)
            outcome = _turn_outcome(state)
            if outcome is None:
                continue
            if outcome.status == "awaiting_input" and on_question is not None:
                answer = on_question(outcome.text)
                message_id = await self.send(session_id, answer)
                delay = _POLL_INITIAL
                continue
            return outcome


class AsyncMedia:
    def __init__(
        self, client: httpx.AsyncClient, upload_client: httpx.AsyncClient, base_url: str
    ) -> None:
        self._client = client
        self._upload_client = upload_client
        self._base = base_url.rstrip("/")

    async def upload(self, data: bytes, extension: str, type: str = "image") -> str:
        resp = await self._client.post(
            f"{self._base}/v1/agent/media",
            json={"extension": extension, "type": type},
        )
        raise_for_agent_status(resp)
        slot = resp.json()
        put = await self._upload_client.put(
            slot["upload_url"],
            content=data,
            headers={"Content-Type": slot["content_type"]},
        )
        put.raise_for_status()
        confirm = await self._client.post(
            f"{self._base}/v1/agent/media/{slot['id']}/confirm",
            json={"type": type},
        )
        raise_for_agent_status(confirm)
        if confirm.json().get("status") != "uploaded":
            raise AgentError("Agent media upload has not been confirmed by the server")
        return slot["url"]


class AsyncAgentsResource:
    """``client.agents`` — async Agent API namespace."""

    def __init__(
        self, client: httpx.AsyncClient, upload_client: httpx.AsyncClient, base_url: str
    ) -> None:
        self.sessions = AsyncSessions(client, base_url)
        self.media = AsyncMedia(client, upload_client, base_url)
