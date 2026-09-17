from __future__ import annotations

import asyncio
import logging
import os
import time
from functools import cached_property
from typing import AsyncIterator, Callable, Dict, Iterator, Optional, Tuple, TYPE_CHECKING

import httpx

from higgsfield_client.auth import get_credential_key
from higgsfield_client.http.error import raise_for_status
from higgsfield_client.http.retry import create_default_retry_strategy
from higgsfield_client.http.transport import AsyncHttpTransport, HttpTransport
from higgsfield_client.mixins import UploadMixin
from higgsfield_client.types_ import (
    AnyJSON,
    Cancelled,
    Completed,
    Failed,
    NSFW,
    Status,
)
from higgsfield_client.utils import get_status, get_url

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from PIL import Image


DEFAULT_TIMEOUT = 90.0
DEFAULT_POLLING_DELAY = 0.5

BASE_URL = 'https://api.higgsfield.ai'
USER_AGENT = "higgsfield-client-py/1.0"
DONE_STATUSES = (Completed, NSFW, Cancelled, Failed)


class RequestController:
    def __init__(
        self,
        request_id: str,
        response_url: Optional[str] = None,
        status_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
    ) -> None:
        self.request_id = request_id

        urls = self.build_urls(BASE_URL, request_id)

        self.response_url = response_url or urls['response_url']
        self.status_url = status_url or urls['status_url']
        self.cancel_url = cancel_url or urls['cancel_url']

    @staticmethod
    def build_urls(base_url: str, request_id: str) -> Dict[str, str]:
        request_base = f'{base_url}/requests/{request_id}'
        return {
            'status_url': f'{request_base}/status',
            'response_url': f'{request_base}/status',
            'cancel_url': f'{request_base}/cancel',
        }


class SyncRequestController(RequestController):
    def __init__(
        self,
        request_id: str,
        transport: HttpTransport,
        response_url: Optional[str] = None,
        status_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
    ) -> None:
        super().__init__(
            request_id=request_id,
            response_url=response_url,
            status_url=status_url,
            cancel_url=cancel_url,
        )
        self._transport = transport

    def cancel(self) -> None:
        self._transport.request('POST', self.cancel_url)

    def status(self) -> Status:
        response = self._transport.request('GET', self.status_url)
        return get_status(response.json())

    def poll_request_status(self, *, delay: float = DEFAULT_POLLING_DELAY) -> Iterator[Status]:
        while True:
            status = self.status()
            yield status

            if isinstance(status, DONE_STATUSES):
                break

            time.sleep(delay)

    def get(self) -> AnyJSON:
        for _ in self.poll_request_status():
            continue

        response = self._transport.request('GET', self.response_url)
        return response.json()

    def __repr__(self):
        return f'SyncRequestController(request_id={self.request_id})'


class AsyncRequestController(RequestController):
    def __init__(
        self,
        request_id: str,
        transport: AsyncHttpTransport,
        response_url: Optional[str] = None,
        status_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
    ) -> None:
        super().__init__(
            request_id=request_id,
            response_url=response_url,
            status_url=status_url,
            cancel_url=cancel_url,
        )
        self._transport = transport

    async def cancel(self) -> None:
        await self._transport.request('POST', self.cancel_url)

    async def status(self) -> Status:
        response = await self._transport.request('GET', self.status_url)
        return get_status(response.json())

    async def poll_request_status(
        self,
        *,
        delay: float = DEFAULT_POLLING_DELAY,
    ) -> AsyncIterator[Status]:
        while True:
            status = await self.status()
            yield status

            if isinstance(status, DONE_STATUSES):
                break

            await asyncio.sleep(delay)

    async def get(self) -> AnyJSON:
        async for _ in self.poll_request_status():
            continue

        response = await self._transport.request('GET', self.response_url)
        return response.json()

    def __repr__(self):
        return f'AsyncRequestController(request_id={self.request_id})'


class SyncClient(UploadMixin):
    def __init__(
        self,
        base_url: str = BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        api_key: str | None = None,
    ):
        self.base_url = base_url
        self.timeout = timeout
        self.api_key = api_key

    @cached_property
    def _client(self) -> httpx.Client:
        api_key = self.api_key or get_credential_key()

        return httpx.Client(
            headers={
                'Authorization': f'Key {api_key}',
                'Content-Type': 'application/json',
                'User-Agent': USER_AGENT,
            },
            timeout=self.timeout,
            base_url=self.base_url,
        )

    @cached_property
    def _upload_client(self) -> httpx.Client:
        return httpx.Client(timeout=self.timeout)

    @cached_property
    def _transport(self) -> HttpTransport:
        retry_strategy = create_default_retry_strategy()
        return HttpTransport(self._client, retry_strategy)

    def get_request_controller(self, request_id: str) -> SyncRequestController:
        return SyncRequestController(request_id, self._transport)

    def submit(
        self,
        application: str,
        arguments: AnyJSON,
        *,
        webhook_url: str | None = None,
    ) -> SyncRequestController:
        """
        This method sends your arguments (as JSON) to the application endpoint and
        returns a request controller that allows you to monitor the request status
        and retrieve results once processing is complete.

        Returns:
            SyncRequestController: A controller object to manage and track the request.
        """
        url = get_url(application, webhook_url)

        response = self._transport.request(
            'POST',
            url,
            json=arguments,
            timeout=self.timeout,
        )

        data = response.json()

        return SyncRequestController(
            request_id=data['request_id'],
            response_url=data['status_url'],
            status_url=data['status_url'],
            cancel_url=data['cancel_url'],
            transport=self._transport,
        )

    def subscribe(
        self,
        application: str,
        arguments: AnyJSON,
        *,
        on_enqueue: Optional[Callable[[str], None]] = None,
        on_queue_update: Optional[Callable[[Status], None]] = None,
    ) -> AnyJSON:
        """
        Submit a request and wait for it to complete, returning the final result.
        Optional callbacks can be provided to monitor progress.

        Args:
            application: The name or identifier of the application to run.
            arguments: Dictionary of parameters to pass to the application.
            on_enqueue: Optional callback invoked when the request is enqueued.
            on_queue_update: Optional callback that receives the current status during polling until the request completes.

        Returns:
            AnyJSON: The JSON response of the completed request.
        """  # noqa: E501
        request_controller = self.submit(application=application, arguments=arguments)

        if on_enqueue is not None:
            on_enqueue(request_controller.request_id)

        if on_queue_update is not None:
            for status in request_controller.poll_request_status():
                on_queue_update(status)

        return request_controller.get()

    def status(self, request_id: str) -> Status:
        """
        Get the current status of a request.

        Args:
            request_id: The unique identifier of the request.

        Returns:
            Status: The current status object
        """
        request_controller = self.get_request_controller(request_id)
        return request_controller.status()

    def result(self, request_id: str) -> AnyJSON:
        """
        Wait for a request to complete and retrieve its result.

        Args:
            request_id: The unique identifier of the request.

        Returns:
            AnyJSON: The JSON response of the completed request.
        """
        request_controller = self.get_request_controller(request_id)
        return request_controller.get()

    def cancel(self, request_id: str) -> None:
        """
        Cancel a request.

        Note: Requests that have already started processing cannot be cancelled.
        A 400 error will be returned if the request cannot be cancelled.

        Args:
            request_id: The unique identifier of the request to cancel.
        """
        request_controller = self.get_request_controller(request_id)
        request_controller.cancel()

    def _get_upload_url(self, content_type: str) -> Tuple[str, str, Dict[str, str]]:
        """
        Request a pre-signed upload URL for a file.

        This method sends the file's content type to the backend and receives:
            public_url — the final URL where the uploaded file will be accessible
            upload_url — the temporary URL to which the file data must be uploaded

        Args:
            content_type: MIME type of the file being uploaded (e.g., 'image/png').

        Returns:
            A tuple (public_url, upload_url, upload_headers).
        """
        response = self._transport.request(
            'POST',
            '/files/generate-upload-url',
            json={'content_type': content_type}
        )
        raise_for_status(response)
        response = response.json()

        upload_headers = response.get('upload_headers') or {'Content-Type': content_type}
        return response['public_url'], response['upload_url'], upload_headers

    def upload(
        self,
        data: bytes | str,
        content_type: str,
    ) -> str:
        """
        Upload this blob and return the URL where it can be accessed.

        Args:
            data: The data to upload (bytes or string)
            content_type: MIME type of the content

        Returns:
            str: The URL where the file can be accessed
        """
        data = self.ensure_bytes(data)

        public_url, upload_url, upload_headers = self._get_upload_url(content_type)

        response = self._upload_client.put(
            upload_url,
            content=data,
            headers=upload_headers,
        )
        raise_for_status(response)

        return public_url

    def upload_file(self, path: os.PathLike) -> str:
        """
        Upload a file from the local filesystem and return the URL where it can be accessed.

        Args:
            path: Path to the file to upload. May be any os.PathLike (e.g., str or Path).

        Returns:
            str: The URL where the file can be accessed
        """
        mime_type = self.guess_mime_type(path)

        with open(path, 'rb') as file:
            return self.upload(file.read(), mime_type)

    def upload_image(self, image: Image.Image, format: str = 'jpeg') -> str:
        """
        Upload an image object and return the URL where it can be accessed.

        Args:
            image: The Pillow Image object.
            format: The format of the image. Defaults to 'jpeg'.

        Returns:
            str: The URL where the image can be accessed.
        """
        image_bytes = self.image_to_bytes(image, format)
        return self.upload(image_bytes, f'image/{format}')


class AsyncClient(UploadMixin):
    def __init__(
        self,
        base_url: str = BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        api_key: str | None = None,
    ):
        self.base_url = base_url
        self.timeout = timeout
        self.api_key = api_key

    @cached_property
    def _client(self) -> httpx.AsyncClient:
        api_key = self.api_key or get_credential_key()

        return httpx.AsyncClient(
            headers={
                'Authorization': f'Key {api_key}',
                'Content-Type': 'application/json',
                'User-Agent': USER_AGENT,
            },
            timeout=self.timeout,
            base_url=self.base_url,
        )

    @cached_property
    def _upload_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self.timeout)

    @cached_property
    def _transport(self) -> AsyncHttpTransport:
        retry_strategy = create_default_retry_strategy()
        return AsyncHttpTransport(self._client, retry_strategy)

    def get_request_controller(self, request_id: str) -> AsyncRequestController:
        return AsyncRequestController(request_id, self._transport)

    async def submit(
        self,
        application: str,
        arguments: AnyJSON,
        *,
        webhook_url: str | None = None,
    ) -> AsyncRequestController:
        """
        This method sends your arguments (as JSON) to the application endpoint and
        returns a request controller that allows you to monitor the request status
        and retrieve results once processing is complete.

        Returns:
            AsyncRequestController: A controller object to manage and track the request.
        """
        url = get_url(application, webhook_url)

        response = await self._transport.request(
            'POST',
            url,
            json=arguments,
            timeout=self.timeout,
        )

        data = response.json()

        return AsyncRequestController(
            request_id=data['request_id'],
            response_url=data['status_url'],
            status_url=data['status_url'],
            cancel_url=data['cancel_url'],
            transport=self._transport,
        )

    async def subscribe(
        self,
        application: str,
        arguments: AnyJSON,
        *,
        on_enqueue: Optional[Callable[[str], None]] = None,
        on_queue_update: Optional[Callable[[Status], None]] = None,
    ) -> AnyJSON:
        """
        Submit a request and wait for it to complete, returning the final result.
        Optional callbacks can be provided to monitor progress.

        Args:
            application: The name or identifier of the application to run.
            arguments: Dictionary of parameters to pass to the application.
            on_enqueue: Optional callback invoked when the request is enqueued.
            on_queue_update: Optional callback that receives the current status during polling until the request completes.

        Returns:
            AnyJSON: The JSON response of the completed request.
        """  # noqa: E501
        request_controller = await self.submit(application=application, arguments=arguments)

        if on_enqueue is not None:
            on_enqueue(request_controller.request_id)

        if on_queue_update is not None:
            async for status in request_controller.poll_request_status():
                on_queue_update(status)

        return await request_controller.get()

    async def status(self, request_id: str) -> Status:
        """
        Get the current status of a request.

        Args:
            request_id: The unique identifier of the request.

        Returns:
            Status: The current status object
        """
        request_controller = self.get_request_controller(request_id)
        return await request_controller.status()

    async def result(self, request_id: str) -> AnyJSON:
        """
        Wait for a request to complete and retrieve its result.

        Args:
            request_id: The unique identifier of the request.

        Returns:
            AnyJSON: The JSON response of the completed request.
        """
        request_controller = self.get_request_controller(request_id)
        return await request_controller.get()

    async def cancel(self, request_id: str) -> None:
        """
        Cancel a request.

        Note: Requests that have already started processing cannot be cancelled.
        A 400 error will be returned if the request cannot be cancelled.

        Args:
            request_id: The unique identifier of the request to cancel.
        """
        request_controller = self.get_request_controller(request_id)
        await request_controller.cancel()

    async def _get_upload_url(self, content_type: str) -> Tuple[str, str, Dict[str, str]]:
        """
        Request a pre-signed upload URL for a file.

        This method sends the file's content type to the backend and receives:
            public_url — the final URL where the uploaded file will be accessible
            upload_url — the temporary URL to which the file data must be uploaded

        Args:
            content_type: MIME type of the file being uploaded (e.g., 'image/png').

        Returns:
            A tuple (public_url, upload_url, upload_headers).
        """
        response = await self._transport.request(
            'POST',
            '/files/generate-upload-url',
            json={'content_type': content_type},
        )
        raise_for_status(response)
        response = response.json()

        upload_headers = response.get('upload_headers') or {'Content-Type': content_type}
        return response['public_url'], response['upload_url'], upload_headers

    async def upload(
        self,
        data: bytes | str,
        content_type: str,
    ) -> str:
        """
        Upload this blob and return the URL where it can be accessed.

        Args:
            data: The data to upload (bytes or string)
            content_type: MIME type of the content

        Returns:
            str: The URL where the file can be accessed
        """
        data = self.ensure_bytes(data)

        public_url, upload_url, upload_headers = await self._get_upload_url(content_type)

        response = await self._upload_client.put(
            upload_url,
            content=data,
            headers=upload_headers,
        )
        raise_for_status(response)

        return public_url

    async def upload_file(self, path: os.PathLike) -> str:
        """
        Upload a file from the local filesystem and return the URL where it can be accessed.

        Args:
            path: Path to the file to upload. May be any os.PathLike (e.g., str or Path).

        Returns:
            str: The URL where the file can be accessed
        """
        mime_type = self.guess_mime_type(path)

        with open(path, 'rb') as file:
            return await self.upload(file.read(), mime_type)

    async def upload_image(self, image: Image.Image, format: str = 'jpeg') -> str:
        """
        Upload an image object and return the URL where it can be accessed.

        Args:
            image: The Pillow Image object.
            format: The format of the image. Defaults to 'jpeg'.

        Returns:
            str: The URL where the image can be accessed.
        """
        image_bytes = self.image_to_bytes(image, format)
        return await self.upload(image_bytes, f'image/{format}')
