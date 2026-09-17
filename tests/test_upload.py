import asyncio
import json
import unittest
from functools import partial
from unittest.mock import patch

import httpx

from higgsfield_client.http.client import AsyncClient, SyncClient


class UploadHeadersTest(unittest.TestCase):
    def check_upload(self, asynchronous, upload_headers):
        calls = []
        public_url = 'https://cdn.example/input.jpg'
        upload_url = 'https://storage.example/upload?signature=test'

        def handle(request):
            calls.append(request)
            if request.url.host == 'api.higgsfield.ai':
                self.assertEqual(request.method, 'POST')
                self.assertEqual(request.url.path, '/files/generate-upload-url')
                self.assertEqual(request.headers['Authorization'], 'Key test:secret')
                self.assertEqual(json.loads(request.content), {'content_type': 'image/jpeg'})
                payload = {'public_url': public_url, 'upload_url': upload_url}
                if upload_headers is not None:
                    payload['upload_headers'] = upload_headers
                return httpx.Response(200, json=payload)

            self.assertEqual(str(request.url), upload_url)
            self.assertEqual(request.method, 'PUT')
            self.assertEqual(request.content, b'image bytes')
            self.assertNotIn('Authorization', request.headers)
            expected = upload_headers or {'Content-Type': 'image/jpeg'}
            for name, value in expected.items():
                self.assertEqual(request.headers.get(name), value)
            return httpx.Response(200)

        transport = httpx.MockTransport(handle)
        if asynchronous:
            async def upload():
                client = AsyncClient(api_key='test:secret')
                try:
                    return await client.upload(b'image bytes', 'image/jpeg')
                finally:
                    await client._client.aclose()
                    await client._upload_client.aclose()

            factory = partial(httpx.AsyncClient, transport=transport)
            with patch('higgsfield_client.http.client.httpx.AsyncClient', factory):
                result = asyncio.run(upload())
        else:
            factory = partial(httpx.Client, transport=transport)
            with patch('higgsfield_client.http.client.httpx.Client', factory):
                client = SyncClient(api_key='test:secret')
                try:
                    result = client.upload(b'image bytes', 'image/jpeg')
                finally:
                    client._client.close()
                    client._upload_client.close()

        self.assertEqual(result, public_url)
        self.assertEqual(len(calls), 2)

    def test_upload_preserves_server_headers(self):
        for asynchronous in (False, True):
            with self.subTest(asynchronous=asynchronous):
                self.check_upload(asynchronous, {
                    'content-type': 'image/jpg',
                    'x-amz-tagging': 'retention=temporary',
                    'x-amz-meta-example': 'preserve-me',
                })

    def test_upload_without_server_headers(self):
        for asynchronous in (False, True):
            for headers in (None, {}):
                with self.subTest(asynchronous=asynchronous, headers=headers):
                    self.check_upload(asynchronous, headers)
