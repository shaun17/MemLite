"""Project API bindings for the MemLite Python SDK."""

from __future__ import annotations

from memolite.api.schemas import ProjectCreateRequest, ProjectResponse


class MemLiteProjectAPI:
    """Project operations."""

    def __init__(self, client) -> None:
        self._client = client

    async def create(
        self,
        *,
        org_id: str,
        project_id: str,
        description: str | None = None,
    ) -> None:
        payload = ProjectCreateRequest(
            org_id=org_id,
            project_id=project_id,
            description=description,
        )
        await self._client.request("POST", "/projects", json=payload.model_dump())

    async def get(self, *, org_id: str, project_id: str) -> ProjectResponse:
        data = await self._client.request("GET", f"/projects/{org_id}/{project_id}")
        return ProjectResponse.model_validate(data)

    async def list(self, *, org_id: str | None = None) -> list[ProjectResponse]:
        params = {"org_id": org_id} if org_id is not None else None
        data = await self._client.request("GET", "/projects", params=params)
        return [ProjectResponse.model_validate(item) for item in data]

    async def delete(self, *, org_id: str, project_id: str) -> None:
        await self._client.request("DELETE", f"/projects/{org_id}/{project_id}")

    async def episode_count(self, *, org_id: str, project_id: str) -> int:
        data = await self._client.request(
            "GET",
            f"/projects/{org_id}/{project_id}/episodes/count",
        )
        return int(data["count"])
