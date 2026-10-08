from io import BytesIO
from pathlib import Path
import os
import tempfile
import zipfile

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pillow_heif import register_heif_opener
from PIL import Image, ImageOps
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from app.auth import require_user
from app.database import get_session
from app.models import Face, Photo, PhotoSource, Project, User
from app.runtime import application_data_dir
from app.services.face_indexer import embedding_from_bytes, google_photo_bytes, local_photo_path
from app.services.face_matching import SEARCH_THRESHOLDS, find_similar_faces

register_heif_opener()
router = APIRouter(prefix="/media", tags=["media"])
bulk_router = APIRouter(prefix="/projects", tags=["media"])
CACHE_ROOT = application_data_dir() / "cache" / "previews"
BULK_TEMP_ROOT = application_data_dir() / "temp" / "downloads"


def _resolve_photo(photo_id: int, session: Session):
    photo = session.get(Photo, photo_id)
    if not photo: raise HTTPException(404, "Photo not found")
    source = session.get(PhotoSource, photo.source_id)
    if not source or source.project_id != photo.project_id: raise HTTPException(404, "Photo source not found")
    return photo, source


def _drive_bytes(session, source, photo):
    try: return google_photo_bytes(session, source, photo)
    except Exception as exc: raise HTTPException(502, f"Unable to retrieve Google Drive photo: {photo.name}") from exc


def _original_bytes(session, photo, source):
    if source.source_type == "local_folder":
        try: return local_photo_path(source, photo).read_bytes()
        except FileNotFoundError as exc: raise HTTPException(404, str(exc)) from exc
        except ValueError as exc: raise HTTPException(400, str(exc)) from exc
    if source.source_type == "google_drive": return _drive_bytes(session, source, photo)
    raise HTTPException(400, "Unsupported storage provider")


def _photo_image(session, photo, source):
    try:
        with Image.open(BytesIO(_original_bytes(session, photo, source))) as image: return ImageOps.exif_transpose(image).convert("RGB")
    except HTTPException: raise
    except Exception as exc: raise HTTPException(415, "Image could not be rendered") from exc


def _cache_path(kind, item_id): return CACHE_ROOT / kind / f"{item_id}.jpg"
def _remove_temp_file(path):
    try: os.unlink(path)
    except FileNotFoundError: pass


def _write_cache(path, data):
    path.parent.mkdir(parents=True, exist_ok=True); fd, temp_name = tempfile.mkstemp(prefix=f".{path.stem}-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle: handle.write(data); handle.flush(); os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        _remove_temp_file(temp_name); raise


def _cached_jpeg(path):
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control":"private, max-age=86400"}) if path.is_file() else None


def _safe_zip_name(name, photo_id, used):
    base=Path(name).name.replace("\x00","") or f"photo-{photo_id}"; candidate=base; stem=Path(base).stem or f"photo-{photo_id}"; suffix=Path(base).suffix; counter=2
    while candidate.casefold() in used: candidate=f"{stem}-{counter}{suffix}"; counter+=1
    used.add(candidate.casefold()); return candidate


@router.get("/faces/{face_id}")
def preview_face(face_id: int, session: Session = Depends(get_session), _: User = Depends(require_user)):
    face=session.get(Face,face_id)
    if not face: raise HTTPException(404,"Face not found")
    photo,source=_resolve_photo(face.photo_id,session); cache_path=_cache_path("faces",face_id)
    if source.source_type=="google_drive":
        cached=_cached_jpeg(cache_path)
        if cached:return cached
    image=_photo_image(session,photo,source); pad_x=max(12,int(face.bbox_w*.35));pad_y=max(12,int(face.bbox_h*.35));left=max(0,face.bbox_x-pad_x);top=max(0,face.bbox_y-pad_y);right=min(image.width,face.bbox_x+face.bbox_w+pad_x);bottom=min(image.height,face.bbox_y+face.bbox_h+pad_y)
    if right<=left or bottom<=top: raise HTTPException(422,"Stored face crop is invalid")
    crop=image.crop((left,top,right,bottom));crop.thumbnail((480,480));output=BytesIO();crop.save(output,format="JPEG",quality=86,optimize=True);data=output.getvalue()
    if source.source_type=="google_drive":_write_cache(cache_path,data)
    return Response(data,media_type="image/jpeg",headers={"Cache-Control":"private, max-age=900"})


@router.get("/photos/{photo_id}")
def preview_photo(photo_id:int,session:Session=Depends(get_session),_:User=Depends(require_user)):
    photo,source=_resolve_photo(photo_id,session)
    if source.source_type=="local_folder":
        try:return FileResponse(local_photo_path(source,photo),media_type=photo.mime_type or None,filename=None)
        except FileNotFoundError as exc:raise HTTPException(404,str(exc)) from exc
        except ValueError as exc:raise HTTPException(400,str(exc)) from exc
    if source.source_type=="google_drive":
        cache_path=_cache_path("photos",photo_id);cached=_cached_jpeg(cache_path)
        if cached:return cached
        try:
            with Image.open(BytesIO(_drive_bytes(session,source,photo))) as image:
                corrected=ImageOps.exif_transpose(image).convert("RGB");corrected.thumbnail((1600,1600));output=BytesIO();corrected.save(output,format="JPEG",quality=88,optimize=True)
            preview=output.getvalue();_write_cache(cache_path,preview);return Response(preview,media_type="image/jpeg",headers={"Cache-Control":"private, max-age=300"})
        except HTTPException:raise
        except Exception as exc:raise HTTPException(415,"Google Drive image could not be rendered") from exc
    raise HTTPException(400,"Unsupported storage provider")


@router.get("/photos/{photo_id}/download")
def download_photo(photo_id:int,session:Session=Depends(get_session),_:User=Depends(require_user)):
    photo,source=_resolve_photo(photo_id,session)
    if source.source_type=="local_folder":
        try:return FileResponse(local_photo_path(source,photo),media_type=photo.mime_type or "application/octet-stream",filename=photo.name)
        except FileNotFoundError as exc:raise HTTPException(404,str(exc)) from exc
        except ValueError as exc:raise HTTPException(400,str(exc)) from exc
    if source.source_type=="google_drive":
        safe_name=photo.name.replace(chr(34),"");return Response(_drive_bytes(session,source,photo),media_type=photo.mime_type or "application/octet-stream",headers={"Content-Disposition":f'attachment; filename="{safe_name}"'})
    raise HTTPException(400,"Unsupported storage provider")


@bulk_router.get("/{project_id}/faces/{face_id}/matches/download")
def download_face_matches(project_id:int,face_id:int,source_id:int|None=Query(None),mode:str=Query("recommended"),session:Session=Depends(get_session),_:User=Depends(require_user)):
    project=session.get(Project,project_id)
    if not project:raise HTTPException(404,"Project not found")
    reference_face=session.get(Face,face_id)
    if not reference_face or reference_face.project_id!=project_id:raise HTTPException(404,"Face not found")
    if mode not in SEARCH_THRESHOLDS:raise HTTPException(400,"Invalid search mode")
    if source_id is not None:
        source=session.get(PhotoSource,source_id)
        if not source or source.project_id!=project_id:raise HTTPException(400,"Selected source does not belong to this project")
    reference=embedding_from_bytes(reference_face.embedding,reference_face.embedding_dim);scope=(source_id,) if source_id is not None else ();matches=find_similar_faces(session,project_id,reference,scope,mode);photo_ids=[];seen=set()
    for face,_score in matches:
        if face.photo_id not in seen:seen.add(face.photo_id);photo_ids.append(face.photo_id)
    if not photo_ids:raise HTTPException(404,"No matched photos to download")
    BULK_TEMP_ROOT.mkdir(parents=True,exist_ok=True);fd,temp_name=tempfile.mkstemp(prefix=f"face-{face_id}-{mode}-",suffix=".zip",dir=str(BULK_TEMP_ROOT));os.close(fd);used_names=set();failures=[]
    try:
        with zipfile.ZipFile(temp_name,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as bundle:
            for photo_id in photo_ids:
                photo,source=_resolve_photo(photo_id,session)
                try:
                    if source.source_type=="local_folder":bundle.write(local_photo_path(source,photo),arcname=_safe_zip_name(photo.name,photo.id,used_names))
                    elif source.source_type=="google_drive":data=_drive_bytes(session,source,photo);bundle.writestr(_safe_zip_name(photo.name,photo.id,used_names),data);del data
                    else:failures.append(f"{photo.name}: unsupported storage provider")
                except (HTTPException,FileNotFoundError,ValueError) as exc:failures.append(f"{photo.name}: {exc.detail if isinstance(exc,HTTPException) else str(exc)}")
            if failures:bundle.writestr("download-errors.txt","Some originals could not be retrieved:\n\n"+"\n".join(failures))
    except Exception:_remove_temp_file(temp_name);raise
    safe_project="".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in project.name).strip("-") or f"project-{project_id}";filename=f"{safe_project}-face-{face_id}-{mode}-matches.zip"
    return FileResponse(temp_name,media_type="application/zip",filename=filename,headers={"Cache-Control":"no-store"},background=BackgroundTask(_remove_temp_file,temp_name))
