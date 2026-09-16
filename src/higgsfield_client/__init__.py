import os

from higgsfield_client.exceptions import (
    CredentialsMissedError,
    HiggsfieldClientError,
)
from higgsfield_client.http.client import (
    BASE_URL,
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

_base_url = os.getenv('HF_BASE_URL') or BASE_URL

sync_client = SyncClient(base_url=_base_url)
submit = sync_client.submit
subscribe = sync_client.subscribe
status = sync_client.status
result = sync_client.result
cancel = sync_client.cancel
upload = sync_client.upload
upload_file = sync_client.upload_file
upload_image = sync_client.upload_image

async_client = AsyncClient(base_url=_base_url)
submit_async = async_client.submit
subscribe_async = async_client.subscribe
status_async = async_client.status
result_async = async_client.result
cancel_async = async_client.cancel
upload_async = async_client.upload
upload_file_async = async_client.upload_file
upload_image_async = async_client.upload_image


__all__ = [
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
