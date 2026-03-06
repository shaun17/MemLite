"""Application error codes for MemLite."""

from enum import StrEnum


class ErrorCode(StrEnum):
    """Stable application-level error codes."""

    INVALID_REQUEST = "invalid_request"
    RESOURCE_NOT_FOUND = "resource_not_found"
    CONFIGURATION_ERROR = "configuration_error"
    INTERNAL_ERROR = "internal_error"
    RESOURCE_NOT_READY = "resource_not_ready"
