"""CLI entrypoints for MemLite MCP servers."""

import asyncio

from memlite.mcp.server import run_http, run_stdio


def run_stdio_main() -> None:
    asyncio.run(run_stdio())


def run_http_main() -> None:
    asyncio.run(run_http())
