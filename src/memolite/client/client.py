"""Core Python SDK client for MemLite."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import httpx

from memolite.client.config import MemLiteConfigAPI
from memolite.client.errors import MemLiteAPIError, MemLiteClientError
from memolite.client.memory import MemLiteMemoryAPI
from memolite.client.projects import MemLiteProjectAPI


class MemLiteClient:
    """Async client for the MemLite REST API."""

    def __init__(
        self,
        *,
        base_url: str,
        timeout: float = 10.0,
        retries: int = 2,
        retry_backoff_seconds: float = 0.05,
        headers: Mapping[str, str] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._retries = retries
        self._retry_backoff_seconds = retry_backoff_seconds
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            headers=dict(headers or {}),
            transport=transport,
        )
        self.projects = MemLiteProjectAPI(self)
        self.memory = MemLiteMemoryAPI(self)
        self.config = MemLiteConfigAPI(self)

    async def __aenter__(self) -> "MemLiteClient":
        return self

    async def __aexit__(self, *_args: object) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, object] | None = None,
        json: Mapping[str, Any] | list[Any] | None = None,
    ) -> Any:
        """Perform a request with basic retry handling."""
        last_error: Exception | None = None
        for attempt in range(self._retries + 1):
            try:
                response = await self._client.request(
                    method=method,
                    url=path,
                    params=params,
                    json=json,
                )
                if response.status_code >= 500 and attempt < self._retries:
                    await asyncio.sleep(self._retry_backoff_seconds * (attempt + 1))
                    continue
                if response.is_error:
                    raise MemLiteAPIError(
                        message=f"{method.upper()} {path} failed",
                        status_code=response.status_code,
                        response_body=self._decode_response(response),
                    )
                return self._decode_response(response)
            except MemLiteAPIError as err:
                if err.status_code >= 500 and attempt < self._retries:
                    last_error = err
                    await asyncio.sleep(self._retry_backoff_seconds * (attempt + 1))
                    continue
                raise
            except httpx.HTTPError as err:
                last_error = err
                if attempt >= self._retries:
                    raise MemLiteClientError(str(err)) from err
                await asyncio.sleep(self._retry_backoff_seconds * (attempt + 1))
        if last_error is not None:
            raise MemLiteClientError(str(last_error)) from last_error
        raise MemLiteClientError("request failed without an error")

    @staticmethod
    def _decode_response(response: httpx.Response) -> Any:
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return response.text
