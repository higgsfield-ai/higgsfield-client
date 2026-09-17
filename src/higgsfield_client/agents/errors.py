from typing import Optional

import httpx


class AgentError(Exception):
    """Base error for the Agent API."""

    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class AgentAccessDeniedError(AgentError):
    """The Agent API is not enabled for this account."""


class InsufficientCreditsError(AgentError):
    """Not enough credits to accept the message."""


class SessionBusyError(AgentError):
    """A turn is already running on this session (HTTP 409)."""


class AgentBackendError(AgentError):
    """The agent backend is temporarily unavailable (retryable)."""


class AgentTimeoutError(AgentError):
    """The turn did not reach a terminal state within the allotted time."""


def raise_for_agent_status(response: httpx.Response) -> None:
    """Map Agent API error responses to typed exceptions."""
    if response.is_success:
        return
    code = response.status_code
    try:
        detail = response.json().get("detail", "")
    except Exception:
        detail = response.text
    if code == 403:
        raise AgentAccessDeniedError(
            "Agent API is not enabled for your account. "
            "Contact support@higgsfield.ai to request access.",
            status_code=code,
        )
    if code == 402:
        raise InsufficientCreditsError(
            f"Insufficient credits: {detail}", status_code=code
        )
    if code == 409:
        raise SessionBusyError(
            "A turn is already running on this session. "
            "Wait for it to finish or interrupt it.",
            status_code=code,
        )
    if code >= 500:
        raise AgentBackendError(
            f"Agent backend unavailable ({code}): {detail}", status_code=code
        )
    response.raise_for_status()
