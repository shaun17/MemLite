import pytest

from memlite.common.retry import retry_async


@pytest.mark.anyio
async def test_retry_async_retries_until_success():
    attempts = {"count": 0}

    async def flaky() -> str:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise ValueError("retry")
        return "ok"

    result = await retry_async(flaky, retries=2, delay_seconds=0.0, retry_on=(ValueError,))

    assert result == "ok"
    assert attempts["count"] == 3


@pytest.mark.anyio
async def test_retry_async_raises_after_exhaustion():
    async def always_fail() -> str:
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        await retry_async(always_fail, retries=1, delay_seconds=0.0, retry_on=(ValueError,))
