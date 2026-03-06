"""Session API routes."""

from fastapi import APIRouter, Depends, HTTPException

from memlite.api.deps import get_resources
from memlite.api.schemas import SessionCreateRequest, SessionResponse, to_session_response
from memlite.app.resources import ResourceManager

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=dict[str, str])
async def create_session(
    payload: SessionCreateRequest,
    resources: ResourceManager = Depends(get_resources),
) -> dict[str, str]:
    await resources.orchestrator.create_session(
        session_key=payload.session_key,
        org_id=payload.org_id,
        project_id=payload.project_id,
        session_id=payload.session_id,
        user_id=payload.user_id,
        agent_id=payload.agent_id,
        group_id=payload.group_id,
    )
    return {"status": "ok"}


@router.get("", response_model=list[SessionResponse])
async def search_sessions(
    org_id: str | None = None,
    project_id: str | None = None,
    user_id: str | None = None,
    agent_id: str | None = None,
    group_id: str | None = None,
    resources: ResourceManager = Depends(get_resources),
) -> list[SessionResponse]:
    sessions = await resources.orchestrator.search_sessions(
        org_id=org_id,
        project_id=project_id,
        user_id=user_id,
        agent_id=agent_id,
        group_id=group_id,
    )
    return [to_session_response(session) for session in sessions]


@router.get("/{session_key}", response_model=SessionResponse)
async def get_session(
    session_key: str,
    resources: ResourceManager = Depends(get_resources),
) -> SessionResponse:
    session = await resources.orchestrator.get_session(session_key)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    return to_session_response(session)


@router.delete("/{session_key}", response_model=dict[str, str])
async def delete_session(
    session_key: str,
    resources: ResourceManager = Depends(get_resources),
) -> dict[str, str]:
    await resources.orchestrator.delete_session(session_key=session_key)
    return {"status": "ok"}
