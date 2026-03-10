"""Minimal example for the MemLite Python SDK."""

import asyncio

from memolite.client import MemLiteClient


async def main() -> None:
    async with MemLiteClient(base_url="http://127.0.0.1:8080") as client:
        await client.projects.create(org_id="demo-org", project_id="demo-project")
        print(await client.projects.list(org_id="demo-org"))


if __name__ == "__main__":
    asyncio.run(main())
