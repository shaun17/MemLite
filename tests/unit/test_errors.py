from memlite.common.error_codes import ErrorCode
from memlite.common.errors import ConfigurationError, ResourceNotReadyError


def test_configuration_error_uses_stable_code():
    error = ConfigurationError("invalid config")

    assert error.code is ErrorCode.CONFIGURATION_ERROR
    assert str(error) == "invalid config"


def test_resource_not_ready_error_uses_stable_code():
    error = ResourceNotReadyError("not ready")

    assert error.code is ErrorCode.RESOURCE_NOT_READY
    assert str(error) == "not ready"
