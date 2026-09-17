import json

import httpx
import pytest

from higgsfield_client.agents.errors import (
    AgentAccessDeniedError,
    SessionBusyError,
)
from higgsfield_client.agents.resources import Sessions
from higgsfield_client.agents.types import AgentMessage, SessionState

BASE = "https://agent.test"
SID = "50eeb94c-c396-439d-b504-aee2147b7ec0"


def _assistant_row(text: str, status: str = "completed") -> dict:
    return {
        "message_id": "a1",
        "role": "assistant",
        "status": status,
        "message": {
            "id": "a1",
            "role": "assistant",
            "parts": [
                {"type": "step-start"},
                {"type": "reasoning", "text": "hidden", "state": "done"},
                {"type": "text", "text": text},
            ],
        },
        "created_at": "2026-09-01T00:00:01Z",
    }


def _sessions(handler) -> Sessions:
    transport = httpx.MockTransport(handler)
    return Sessions(httpx.Client(transport=transport), BASE)


def test_run_returns_completed_turn_with_text_and_assets(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _: None)
    polls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/messages"):
            assert json.loads(request.content)["content"] == "make an image"
            return httpx.Response(
                202, json={"message_id": "u1", "status": "processing"}
            )
        assert request.url.params["after"] == "u1"
        polls["count"] += 1
        if polls["count"] == 1:
            return httpx.Response(200, json={"status": "processing", "messages": []})
        return httpx.Response(
            200,
            json={
                "status": "idle",
                "messages": [_assistant_row("Done: https://cdn.test/a.png.")],
            },
        )

    result = _sessions(handler).run(SID, "make an image")
    assert result.status == "completed"
    # Reasoning/step parts are internals -- only text parts surface.
    assert result.text == "Done: https://cdn.test/a.png."
    # Trailing punctuation is not part of the asset URL.
    assert result.asset_urls == ["https://cdn.test/a.png"]


def test_run_surfaces_question_and_answers_via_handler(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _: None)
    sent = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/messages"):
            body = json.loads(request.content)
            sent.append(body["content"])
            return httpx.Response(
                202, json={"message_id": f"u{len(sent)}", "status": "processing"}
            )
        after = request.url.params["after"]
        if after == "u1":
            # Parked turn: the question is the (non-terminal) assistant row.
            return httpx.Response(
                200,
                json={
                    "status": "awaiting_input",
                    "messages": [_assistant_row("Which style?", status="processing")],
                },
            )
        return httpx.Response(
            200,
            json={"status": "idle", "messages": [_assistant_row("photoreal it is")]},
        )

    result = _sessions(handler).run(
        SID, "make an image", on_question=lambda q: f"answer to: {q}"
    )
    assert sent == ["make an image", "answer to: Which style?"]
    assert result.status == "completed"


def test_run_without_handler_returns_awaiting_input(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _: None)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(
                202, json={"message_id": "u1", "status": "processing"}
            )
        return httpx.Response(
            200,
            json={
                "status": "awaiting_input",
                "messages": [_assistant_row("Which style?", status="processing")],
            },
        )

    result = _sessions(handler).run(SID, "make an image")
    assert result.status == "awaiting_input"
    assert result.text == "Which style?"


def test_busy_session_raises_typed_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"detail": "session_busy"})

    with pytest.raises(SessionBusyError):
        _sessions(handler).send(SID, "hi")


def test_403_maps_to_access_denied():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"detail": "agent_api_access_denied"})

    with pytest.raises(AgentAccessDeniedError):
        _sessions(handler).create()


def test_user_row_text_and_cost_passthrough():
    state = SessionState.from_dict(
        {
            "status": "idle",
            "messages": [
                {
                    "message_id": "u1",
                    "role": "user",
                    "status": "completed",
                    "message": {"type": "text", "text": "hello"},
                    "created_at": "2026-09-01T00:00:00Z",
                    "llm_cost_usd": "0.2626",
                }
            ],
        }
    )
    row = state.messages[0]
    assert isinstance(row, AgentMessage)
    assert row.text == "hello"
    assert row.llm_cost_usd == "0.2626"
