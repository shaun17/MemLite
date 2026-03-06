"""Project API routes."""

from fastapi import APIRouter, Depends, HTTPException

from memlite.api.deps import get_resources
from memlite.api.schemas import ProjectCreateRequest, ProjectResponse, to_project_response
from memlite.app.resources import ResourceManager

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=dict[str, str])
async def create_project(
    payload: ProjectCreateRequest,
    resources: ResourceManager = Depends(get_resources),
) -> dict[str, str]:
    await resources.orchestrator.create_project(
        org_id=payload.org_id,
        project_id=payload.project_id,
        description=payload.description,
    )
    return {"status": "ok"}


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    org_id: str | None = None,
    resources: ResourceManager = Depends(get_resources),
) -> list[ProjectResponse]:
    projects = await resources.orchestrator.list_projects(org_id)
    return [to_project_response(project) for project in projects]


@router.get("/{org_id}/{project_id}", response_model=ProjectResponse)
async def get_project(
    org_id: str,
    project_id: str,
    resources: ResourceManager = Depends(get_resources),
) -> ProjectResponse:
    project = await resources.orchestrator.get_project(
        org_id=org_id,
        project_id=project_id,
    )
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return to_project_response(project)


@router.get("/{org_id}/{project_id}/episodes/count", response_model=dict[str, int])
async def get_project_episode_count(
    org_id: str,
    project_id: str,
    resources: ResourceManager = Depends(get_resources),
) -> dict[str, int]:
    count = await resources.project_store.get_episode_count(org_id, project_id)
    return {"count": count}


@router.delete("/{org_id}/{project_id}", response_model=dict[str, str])
async def delete_project(
    org_id: str,
    project_id: str,
    resources: ResourceManager = Depends(get_resources),
) -> dict[str, str]:
    await resources.orchestrator.delete_project(org_id=org_id, project_id=project_id)
    return {"status": "ok"}
