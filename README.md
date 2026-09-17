# Higgsfield Python Client

The official Python SDK for [Higgsfield AI](https://cloud.higgsfield.ai). Supports both synchronous and asynchronous usage.

## Installation

```bash
pip install higgsfield-client
```

## Authentication

Before using the client, set your API credentials as environment variables. You can use either a single key or separate API key and secret:

**Option 1: Single Key**

```bash
export HF_KEY="your-api-key:your-api-secret"
```

**Option 2: API Key + Secret**

```bash
export HF_API_KEY="your-api-key"
export HF_API_SECRET="your-api-secret"
```

Get your credentials from the [Higgsfield Cloud](https://cloud.higgsfield.ai/).

## Quick Start

**Synchronous:**

```python
import higgsfield_client

# Submit and wait for result
result = higgsfield_client.subscribe(
    'bytedance/seedream/v4/text-to-image',
    arguments={
        'prompt': 'A serene lake at sunset with mountains',
        'resolution': '2K',
        'aspect_ratio': '16:9',
        'camera_fixed': False
    }
)

print(result['images'][0]['url'])
```

**Asynchronous:**

```python
import asyncio

import higgsfield_client

async def main():
    # Submit and wait for result
    result = await higgsfield_client.subscribe_async(
        'bytedance/seedream/v4/text-to-image',
        arguments={
            'prompt': 'A serene lake at sunset with mountains',
            'resolution': '2K',
            'aspect_ratio': '16:9',
            'camera_fixed': False
        }
    )

    print(result['images'][0]['url'])

asyncio.run(main())
```

## Usage Patterns

### Pattern 1: Simple Submit and Wait

Submit a request and wait for the result:

**Synchronous:**

```python
import higgsfield_client

result = higgsfield_client.subscribe(
    'bytedance/seedream/v4/text-to-image',
    arguments={
        'prompt': 'A serene lake at sunset with mountains',
        'resolution': '2K',
        'aspect_ratio': '16:9',
        'camera_fixed': False
    }
)

print(result['images'][0]['url'])
```

**Asynchronous:**

```python
import asyncio

import higgsfield_client

async def main():
    result = await higgsfield_client.subscribe_async(
        'bytedance/seedream/v4/text-to-image',
        arguments={
            'prompt': 'A serene lake at sunset with mountains',
            'resolution': '2K',
            'aspect_ratio': '16:9',
            'camera_fixed': False
        }
    )
    
    print(result['images'][0]['url'])

asyncio.run(main())
```

### Pattern 2: Submit and Track Progress

Submit a request and monitor its status in real-time:

**Synchronous:**

```python
import higgsfield_client

request_controller = higgsfield_client.submit(
    'bytedance/seedream/v4/text-to-image',
    arguments={
        'prompt': 'Football ball',
        'resolution': '2K',
        'aspect_ratio': '16:9',
        'camera_fixed': False
    },
    webhook_url='https://example.com/webhook'  # Optional parameter which calls your webhook on completion
)

for status in request_controller.poll_request_status():
    if isinstance(status, higgsfield_client.Queued):
        print('Queued')
    elif isinstance(status, higgsfield_client.InProgress):
        print('In progress')
    elif isinstance(status, higgsfield_client.Completed):
        print('Completed')
    elif isinstance(status, (higgsfield_client.Failed, higgsfield_client.NSFW, higgsfield_client.Cancelled)):
        print('Oops!')

result = request_controller.get()
print(result['images'][0]['url'])
```

**Asynchronous:**

```python
import asyncio

import higgsfield_client

async def main():
    request_controller = await higgsfield_client.submit_async(
        'bytedance/seedream/v4/text-to-image',
        arguments={
            'prompt': 'Football ball',
            'resolution': '2K',
            'aspect_ratio': '16:9',
            'camera_fixed': False
        },
        webhook_url='https://example.com/webhook'  # Optional parameter which calls your webhook on completion
    )

    async for status in request_controller.poll_request_status():
        if isinstance(status, higgsfield_client.Queued):
            print('Queued')
        elif isinstance(status, higgsfield_client.InProgress):
            print('In progress')
        elif isinstance(status, higgsfield_client.Completed):
            print('Completed')
        elif isinstance(status, (higgsfield_client.Failed, higgsfield_client.NSFW, higgsfield_client.Cancelled)):
            print('Oops!')

    result = await request_controller.get()
    print(result['images'][0]['url'])

asyncio.run(main())
```

### Pattern 3: Submit with Callbacks

Use callbacks to handle status updates:

**Synchronous:**

```python
import higgsfield_client

def on_enqueue(request_id):
    print(f'Request {request_id} was enqueued')

def on_status_update(status):
    print(f'Status: {status}')

result = higgsfield_client.subscribe(
    'bytedance/seedream/v4/text-to-image',
    arguments={
        'prompt': 'A serene lake at sunset with mountains',
        'resolution': '2K',
        'aspect_ratio': '16:9',
        'camera_fixed': False
    },
    on_enqueue=on_enqueue,
    on_queue_update=on_status_update
)
```

**Asynchronous:**

```python
import asyncio

import higgsfield_client

def on_enqueue(request_id):
    print(f'Request {request_id} was enqueued')

def on_status_update(status):
    print(f'Status: {status}')

async def main():
    await higgsfield_client.subscribe_async(
        'bytedance/seedream/v4/text-to-image',
        arguments={
            'prompt': 'A serene lake at sunset with mountains',
            'resolution': '2K',
            'aspect_ratio': '16:9',
            'camera_fixed': False
        },
        on_enqueue=on_enqueue,
        on_queue_update=on_status_update
    )

asyncio.run(main())
```

### Pattern 4: Manage Existing Requests

Work with request controller:

**Synchronous:**

```python
import higgsfield_client

request_controller = higgsfield_client.submit(
    'bytedance/seedream/v4/text-to-image',
    arguments={
        'prompt': 'A serene lake at sunset with mountains',
        'resolution': '2K',
        'aspect_ratio': '16:9',
        'camera_fixed': False
    },
    webhook_url='https://example.com/webhook'  # Optional parameter which calls your webhook on completion
)

# Check status
status = request_controller.status()

# Wait for completion and get result
result = request_controller.get()

# Cancel a queued request
request_controller.cancel()
```

Or by request ID:

```python
import higgsfield_client

# Check status of any request
status = higgsfield_client.status(request_id='cdbe9381-e617-438f-ac99-b18eb52a05a0')

# Wait for completion and get result
result = higgsfield_client.result(request_id='cdbe9381-e617-438f-ac99-b18eb52a05a0')

# Cancel a queued request
higgsfield_client.cancel(request_id='cdbe9381-e617-438f-ac99-b18eb52a05a0')
```

**Asynchronous:**

```python
import asyncio

import higgsfield_client

async def main():
    request_controller = await higgsfield_client.submit_async(
        'bytedance/seedream/v4/text-to-image',
        arguments={
            'prompt': 'A serene lake at sunset with mountains',
            'resolution': '2K',
            'aspect_ratio': '16:9',
            'camera_fixed': False
        },
        webhook_url='https://example.com/webhook'  # Optional parameter which calls your webhook on completion
    )

    # Check status
    status = await request_controller.status()

    # Wait for completion and get result
    result = await request_controller.get()

    # Cancel a queued request
    await request_controller.cancel()

asyncio.run(main())
```

Or by request ID:

```python
import asyncio

import higgsfield_client

async def main():
    # Check status of any request
    status = await higgsfield_client.status_async(request_id='cdbe9381-e617-438f-ac99-b18eb52a05a0')

    # Wait for completion and get result
    result = await higgsfield_client.result_async(request_id='cdbe9381-e617-438f-ac99-b18eb52a05a0')

    # Cancel a queued request
    await higgsfield_client.cancel_async(request_id='cdbe9381-e617-438f-ac99-b18eb52a05a0')

asyncio.run(main())
```


## File Uploads

Upload files to use in your requests:

### Upload bytes

```python
import higgsfield_client

image_path = 'path/to/example.jpeg'
content_type = 'image/jpeg'

with open(image_path, 'rb') as f:
    data = f.read()

url = higgsfield_client.upload(data, content_type)
```

### Upload by path

```python
import higgsfield_client

image_path = 'path/to/example.jpeg'

url = higgsfield_client.upload_file(image_path)
```

### Upload PIL Images

```python
from PIL import Image
import higgsfield_client

image = Image.open('example.jpeg')
url = higgsfield_client.upload_image(image, format='jpeg')
```

### Async Uploads

All upload methods have async versions:

```python
import higgsfield_client

# Async raw data upload
url = await higgsfield_client.upload_async(data, content_type='image/jpeg')

# Async file upload
url = await higgsfield_client.upload_file_async('path/to/example.jpeg')

# Async image upload
url = await higgsfield_client.upload_image_async(image, format='jpeg')
```

## Agent API

The Agent API runs multi-step creative tasks in persistent sessions. Your account
must have Agent API access and enough credits for the turn and its generations.

```python
from higgsfield_client import SyncClient

# Uses HF_KEY or HF_API_KEY + HF_API_SECRET.
client = SyncClient()
session = client.agents.sessions.create()
result = client.agents.sessions.run(
    session.session_id,
    "Generate an image of an alpine lake at sunrise. Reply with the image URL.",
    on_question=lambda question: "Photorealistic style.",
)
print(result.status)  # completed | failed | awaiting_input
print(result.text)
print(result.asset_urls)

with open("photo.jpeg", "rb") as file:
    url = client.agents.media.upload(file.read(), extension="jpeg", type="image")
client.agents.sessions.run(session.session_id, f"Animate this image: {url}")
```

`AsyncClient` exposes the same methods; await each call. Configure credentials
explicitly with `api_key="key-id:key-secret"`, or override `base_url` and `timeout`
on either client as usual. Agent resources use the same API host as generations.

`run()` sends a message and polls with backoff from 2 to 10 seconds. Without an
`on_question` callback, an agent question returns `awaiting_input`; send the answer
in the same session to continue. The callback receives the question text and
returns an answer string (also for `AsyncClient`). A turn defaults to a 30-minute
wait limit, configurable with `run(..., timeout=seconds)`. `AgentTimeoutError`
ends the local wait; the server-side turn keeps running.

For manual control, use `sessions.send()`, `sessions.messages(after=message_id)`,
and `sessions.interrupt()`. Media upload creates a slot, uploads bytes without
API credentials, and confirms the upload before returning its URL.

Errors include `SessionBusyError` (409), `AgentAccessDeniedError` (403),
`InsufficientCreditsError` (402), and `AgentBackendError` (5xx). Mutating calls
are not automatically retried, so a timeout does not silently submit another
billable turn. Other HTTP errors are raised as `httpx.HTTPStatusError`.
