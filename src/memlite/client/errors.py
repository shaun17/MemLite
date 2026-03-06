"""Error models for the MemLite Python SDK."""

from dataclasses import dataclass


@dataclass(slots=True)
class MemLiteClientError(Exception):
    """Base SDK exception."""

    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(slots=True)
class MemLiteAPIError(MemLiteClientError):
    """Raised when the MemLite API returns a non-success response."""

    status_code: int
    response_body: object | None = None
