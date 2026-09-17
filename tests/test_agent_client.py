"""Public-client contracts for Agent API requests and storage uploads."""

import asyncio
import inspect
import json
from functools import partial

import httpx
import pytest

from higgsfield_client import (
    AgentAccessDeniedError,
    AgentBackendError,
    AgentError,
    AgentTimeoutError,
    AsyncClient,
    InsufficientCreditsError,
    SessionBusyError,
    SyncClient,
)


@pytest.fixture(params=[False, True], ids=["sync", "async"])
def sdk(request, monkeypatch):
    asynchronous = request.param
    clients = []

    def call(method, *args, **kwargs):
        value = method(*args, **kwargs)
        return asyncio.run(value) if inspect.isawaitable(value) else value

    def create(handler):
        transport = httpx.MockTransport(handler)
        http_client = httpx.AsyncClient if asynchronous else httpx.Client
        monkeypatch.setattr(
            "higgsfield_client.http.client.httpx." + http_client.__name__,
            partial(http_client, transport=transport),
        )
        client_class = AsyncClient if asynchronous else SyncClient
        client = client_class(base_url="https://agent.test/", api_key="test:secret")
        clients.append(client)
        return client, call

    yield create
    for client in clients:
        for name in ("_client", "_upload_client"):
            if name in client.__dict__:
                raw = client.__dict__[name]
                call(raw.aclose if asynchronous else raw.close)


@pytest.mark.parametrize("question_handler", [False, True])
def test_public_client_runs_session_and_handles_question(
    sdk, monkeypatch, question_handler
):
    monkeypatch.setattr("higgsfield_client.agents.resources.time.sleep", lambda _: None)

    async def no_sleep(_):
        pass

    monkeypatch.setattr("higgsfield_client.agents.resources.asyncio.sleep", no_sleep)
    sent = []
    paths = []

    def handle(request):
        assert request.url.host == "agent.test"
        assert request.headers["Authorization"] == "Key test:secret"
        paths.append(request.url.path)
        if request.url.path == "/v1/agent/sessions":
            assert json.loads(request.content) == {"config": {"style": "photo"}}
            return httpx.Response(201, json={"session_id": "s1", "status": "idle"})
        if request.url.path.endswith("/interrupt"):
            return httpx.Response(202)
        assert request.url.path == "/v1/agent/sessions/s1/messages"
        if request.method == "POST":
            sent.append(json.loads(request.content)["content"])
            return httpx.Response(
                202, json={"message_id": f"u{len(sent)}", "status": "processing"}
            )
        assert request.url.params["after"] == f"u{len(sent)}"
        question = len(sent) == 1
        return httpx.Response(
            200,
            json={
                "status": "awaiting_input" if question else "idle",
                "messages": [
                    {
                        "message_id": "a1",
                        "role": "assistant",
                        "status": "processing" if question else "completed",
                        "message": {
                            "parts": [
                                {"type": "reasoning", "text": "private reasoning"},
                                {
                                    "type": "text",
                                    "text": "Which style?"
                                    if question
                                    else "https://cdn.test/image.png",
                                },
                            ]
                        },
                    }
                ],
            },
        )

    client, call = sdk(handle)
    session = call(client.agents.sessions.create, {"style": "photo"})
    questions = []

    def answer(question):
        questions.append(question)
        return "Photo"

    result = call(
        client.agents.sessions.run,
        session.session_id,
        "Draw a lake",
        on_question=answer if question_handler else None,
    )
    if question_handler:
        assert questions == ["Which style?"]
        assert sent == ["Draw a lake", "Photo"]
        assert result.status == "completed"
        assert result.asset_urls == ["https://cdn.test/image.png"]
    else:
        assert result.status == "awaiting_input"
        assert result.text == "Which style?"
        assert sent == ["Draw a lake"]
    call(client.agents.sessions.interrupt, session.session_id)
    assert paths[-1] == "/v1/agent/sessions/s1/interrupt"


@pytest.mark.parametrize(
    "status,error",
    [
        (402, InsufficientCreditsError),
        (403, AgentAccessDeniedError),
        (409, SessionBusyError),
        (502, AgentBackendError),
        (401, httpx.HTTPStatusError),
    ],
)
def test_agent_errors_do_not_retry_billable_messages(sdk, status, error):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(status, json={"detail": "rejected"})

    client, call = sdk(handle)
    with pytest.raises(error):
        call(client.agents.sessions.send, "s1", "Hello")
    assert len(calls) == 1


@pytest.mark.parametrize(
    "put_status,confirmation", [(200, "uploaded"), (200, "not_ready"), (403, None)]
)
def test_media_upload_requires_success_and_keeps_api_key_out_of_storage(
    sdk, put_status, confirmation
):
    calls = []

    def handle(request):
        calls.append(request)
        if request.url.host == "storage.test":
            assert request.method == "PUT"
            assert str(request.url) == "https://storage.test/upload?signature=test"
            assert "Authorization" not in request.headers
            assert request.headers["Content-Type"] == "image/jpeg"
            assert request.content == b"image bytes"
            return httpx.Response(put_status)
        assert request.headers["Authorization"] == "Key test:secret"
        assert request.url.host == "agent.test"
        if request.url.path.endswith("/confirm"):
            assert request.url.path == "/v1/agent/media/m1.jpeg/confirm"
            assert json.loads(request.content) == {"type": "image"}
            return httpx.Response(200, json={"id": "m1.jpeg", "status": confirmation})
        assert request.url.path == "/v1/agent/media"
        assert json.loads(request.content) == {"extension": "jpeg", "type": "image"}
        return httpx.Response(
            201,
            json={
                "id": "m1.jpeg",
                "content_type": "image/jpeg",
                "upload_url": "https://storage.test/upload?signature=test",
                "url": "https://cdn.test/m1.jpeg",
            },
        )

    client, call = sdk(handle)
    if put_status != 200:
        with pytest.raises(httpx.HTTPStatusError):
            call(client.agents.media.upload, b"image bytes", extension="jpeg")
        assert len(calls) == 2
    elif confirmation != "uploaded":
        with pytest.raises(AgentError, match="not been confirmed"):
            call(client.agents.media.upload, b"image bytes", extension="jpeg")
        assert len(calls) == 3
    else:
        assert (
            call(client.agents.media.upload, b"image bytes", extension="jpeg")
            == "https://cdn.test/m1.jpeg"
        )
        assert len(calls) == 3


def test_run_timeout_does_not_resubmit_or_interrupt(sdk, monkeypatch):
    ticks = iter([0.0, 2.0])

    # Patch this module's clock rather than asyncio's global monotonic clock.
    class Clock:
        @staticmethod
        def monotonic():
            return next(ticks)

    monkeypatch.setattr("higgsfield_client.agents.resources.time", Clock)
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(202, json={"message_id": "u1", "status": "processing"})

    client, call = sdk(handle)
    with pytest.raises(AgentTimeoutError, match="keeps running server-side"):
        call(client.agents.sessions.run, "s1", "Hello", timeout=1)
    assert len(calls) == 1
    assert calls[0].url.path == "/v1/agent/sessions/s1/messages"
