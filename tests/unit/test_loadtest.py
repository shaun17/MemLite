import asyncio

import pytest

from memolite.tools.loadtest import load_test_memory_search


@pytest.mark.anyio
async def test_load_test_memory_search_collects_report():
    async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await reader.read(4096)
        writer.write(
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Length: 2\r\n"
            b"Connection: close\r\n\r\n{}"
        )
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        report = await load_test_memory_search(
            base_url=f"http://127.0.0.1:{port}",
            org_id="org-1",
            project_id="project-1",
            query="recall",
            total_requests=4,
            concurrency=2,
            timeout_seconds=2.0,
        )
    finally:
        server.close()
        await server.wait_closed()

    assert report["total_requests"] == 4
    assert report["concurrency"] == 2
    assert report["success_count"] == 4
    assert report["failure_count"] == 0
    assert report["avg_latency_ms"] >= 0
