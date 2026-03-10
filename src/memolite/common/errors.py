"""Application exceptions for MemLite."""

from dataclasses import dataclass
from typing import Any

from memolite.common.error_codes import ErrorCode


@dataclass(slots=True)
class MemLiteError(Exception):
    """Base exception carrying a stable error code."""

    code: ErrorCode
    message: str
    details: dict[str, Any] | None = None

    def __str__(self) -> str:
        return self.message


class ConfigurationError(MemLiteError):
    """Raised when application configuration is invalid."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(ErrorCode.CONFIGURATION_ERROR, message, details)


class ResourceNotReadyError(MemLiteError):
    """Raised when a runtime dependency is not initialized yet."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(ErrorCode.RESOURCE_NOT_READY, message, details)
