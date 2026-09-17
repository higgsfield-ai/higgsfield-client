from higgsfield_client.agents import (
    AgentAccessDeniedError,
    AgentBackendError,
    AgentError,
    AgentMessage,
    AgentSession,
    AgentTimeoutError,
    InsufficientCreditsError,
    MessageStatus,
    SessionBusyError,
    SessionState,
    SessionStatus,
    TurnResult,
)
from higgsfield_client.exceptions import (
    CredentialsMissedError,
    HiggsfieldClientError,
)
from higgsfield_client.http.client import (
    AsyncClient,
    AsyncRequestController,
    DONE_STATUSES,
    SyncClient,
    SyncRequestController,
)
from higgsfield_client.types_ import (
    Cancelled,
    Completed,
    Failed,
    InProgress,
    NSFW,
    Queued,
    Status,
)

sync_client = SyncClient()
submit = sync_client.submit
subscribe = sync_client.subscribe
status = sync_client.status
result = sync_client.result
cancel = sync_client.cancel
upload = sync_client.upload
upload_file = sync_client.upload_file
upload_image = sync_client.upload_image

async_client = AsyncClient()
submit_async = async_client.submit
subscribe_async = async_client.subscribe
status_async = async_client.status
result_async = async_client.result
cancel_async = async_client.cancel
upload_async = async_client.upload
upload_file_async = async_client.upload_file
upload_image_async = async_client.upload_image


__all__ = [
    'AgentAccessDeniedError',
    'AgentBackendError',
    'AgentError',
    'AgentMessage',
    'AgentSession',
    'AgentTimeoutError',
    'InsufficientCreditsError',
    'MessageStatus',
    'SessionBusyError',
    'SessionState',
    'SessionStatus',
    'TurnResult',
    'CredentialsMissedError',
    'HiggsfieldClientError',
    'SyncRequestController',
    'AsyncRequestController',
    'SyncClient',
    'AsyncClient',
    'DONE_STATUSES',
    'Queued',
    'InProgress',
    'Completed',
    'Status',
    'Failed',
    'Cancelled',
    'NSFW',
    'submit',
    'subscribe',
    'status',
    'result',
    'cancel',
    'upload',
    'upload_file',
    'upload_image',
    'submit_async',
    'subscribe_async',
    'status_async',
    'result_async',
    'cancel_async',
    'upload_async',
    'upload_file_async',
    'upload_image_async',
]
