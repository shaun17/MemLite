import httpx
import pytest

from memolite.client import MemLiteClient
from memolite.client.errors import MemLiteAPIError, MemLiteClientError


@pytest.mark.anyio
async def test_sdk_client_retries_server_errors():
    attempts = {"count": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(503, json={"detail": "retry"})
        return httpx.Response(200, json={"status": "ok"})

    client = MemLiteClient(
        base_url="http://testserver",
        retries=1,
        retry_backoff_seconds=0.0,
        transport=httpx.MockTransport(handler),
    )

    response = await client.request("GET", "/health")

    assert response == {"status": "ok"}
    assert attempts["count"] == 2
    await client.close()


@pytest.mark.anyio
async def test_sdk_client_raises_api_error_on_4xx():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "missing"})

    client = MemLiteClient(
        base_url="http://testserver",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(MemLiteAPIError) as exc_info:
        await client.request("GET", "/projects/org-a/project-a")

    assert exc_info.value.status_code == 404
    assert exc_info.value.response_body == {"detail": "missing"}
    await client.close()


@pytest.mark.anyio
async def test_sdk_client_raises_client_error_after_transport_retries():
    attempts = {"count": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        raise httpx.ConnectError("boom", request=request)

    client = MemLiteClient(
        base_url="http://testserver",
        retries=1,
        retry_backoff_seconds=0.0,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(MemLiteClientError, match="boom"):
        await client.request("GET", "/health")

    assert attempts["count"] == 2
    await client.close()
