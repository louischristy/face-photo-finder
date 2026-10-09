from fastapi import APIRouter, Depends, Form, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_user
from app.database import get_session
from app.models import PhotoSource, Project, User
from app.search_scope import build_search_scope

router = APIRouter(prefix="/projects", tags=["search"])


@router.get("/{project_id}/search-scope")
def search_scope_options(project_id: int, session: Session = Depends(get_session), _: User = Depends(require_user)):
    project = session.get(Project, project_id)
    if not project: raise HTTPException(404, "Project not found")
    sources = session.scalars(select(PhotoSource).where(PhotoSource.project_id == project_id, PhotoSource.active.is_(True))).all()
    return {"project":{"id":project.id,"name":project.name},"default":"all","sources":[{"id":s.id,"type":s.source_type,"name":s.display_name or s.source_uri,"removable_media":s.removable_media} for s in sources]}


@router.post("/{project_id}/search-scope")
def choose_search_scope(project_id:int,source_ids:list[int]|None=Form(None),session:Session=Depends(get_session),_:User=Depends(require_user)):
    if not session.get(Project,project_id):raise HTTPException(404,"Project not found")
    allowed=set(session.scalars(select(PhotoSource.id).where(PhotoSource.project_id==project_id,PhotoSource.active.is_(True))).all());scope=build_search_scope(project_id,source_ids)
    try:scope.validate_for_project(allowed)
    except ValueError as exc:raise HTTPException(400,str(exc)) from exc
    selected="all" if scope.all_sources else ",".join(map(str,scope.source_ids));return RedirectResponse(f"/ui/projects/{project_id}?scope={selected}",status_code=303)


@router.get("/{project_id}/search/validate")
def validate_search_scope(project_id:int,source_id:list[int]|None=Query(None),session:Session=Depends(get_session),_:User=Depends(require_user)):
    if not session.get(Project,project_id):raise HTTPException(404,"Project not found")
    allowed=set(session.scalars(select(PhotoSource.id).where(PhotoSource.project_id==project_id)).all());scope=build_search_scope(project_id,source_id)
    try:scope.validate_for_project(allowed)
    except ValueError as exc:raise HTTPException(400,str(exc)) from exc
    return {"project_id":project_id,"all_sources":scope.all_sources,"source_ids":list(scope.source_ids)}
