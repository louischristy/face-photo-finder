from html import escape
import math

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_user
from app.database import get_session
from app.models import Face, Photo, PhotoSource, Project, User
from app.services.face_indexer import embedding_from_bytes
from app.services.face_matching import SEARCH_THRESHOLDS, find_similar_faces
from app.settings import get_app_settings
from app.ui import page

router = APIRouter(prefix="/projects", tags=["gallery"])
PAGE_SIZE = 48
DEDUP_THRESHOLDS = {"conservative": 0.66, "normal": 0.58, "aggressive": 0.52}
EMPTY_GALLERY = '<div class="card">No detected faces in this scope.</div>'
EMPTY_MATCHES = '<div class="card">No similar photos met this search threshold.</div>'


def _project_sources(session: Session, project_id: int):
    return session.scalars(select(PhotoSource).where(PhotoSource.project_id == project_id).order_by(PhotoSource.id)).all()


def _validate_source(sources, source_id: int | None):
    if source_id is not None and source_id not in {source.id for source in sources}:
        raise HTTPException(400, "Selected source does not belong to this project")


def _source_options(sources, source_id: int | None):
    options = ['<option value="">All indexed sources</option>']
    for source in sources:
        selected = " selected" if source.id == source_id else ""
        options.append(f'<option value="{source.id}"{selected}>{escape(source.display_name or source.source_type)}</option>')
    return "".join(options)


def _dedup_options(selected_mode: str):
    labels = {"conservative": "Conservative", "normal": "Normal", "aggressive": "Aggressive"}
    return "".join(f'<option value="{name}"{" selected" if name == selected_mode else ""}>{labels[name]} ({threshold:.2f})</option>' for name, threshold in DEDUP_THRESHOLDS.items())


def _face_quality(face: Face) -> float:
    confidence = max(0.0, min(float(face.detector_score or 0.0), 1.0)); area = max(0, int(face.bbox_w or 0)) * max(0, int(face.bbox_h or 0)); size_score = min(math.sqrt(area) / 400.0, 1.0) if area else 0.0
    return (confidence * 0.72) + (size_score * 0.28)


def _normalized_embedding(face: Face) -> np.ndarray:
    vector = embedding_from_bytes(face.embedding, face.embedding_dim).astype(np.float32, copy=True).flatten(); norm = float(np.linalg.norm(vector))
    if norm: vector /= norm
    return vector


def _representative_faces(faces: list[Face], threshold: float) -> tuple[list[Face], int]:
    representatives=[]; vectors=[]; suppressed=0
    for face in faces:
        vector=_normalized_embedding(face)
        if any(candidate.shape == vector.shape and float(np.dot(vector, candidate)) >= threshold for candidate in vectors): suppressed += 1; continue
        representatives.append(face); vectors.append(vector)
    return representatives, suppressed


def _ordered_photo_matches(session, project_id, reference_face, source_id, mode):
    reference=embedding_from_bytes(reference_face.embedding, reference_face.embedding_dim); scope=(source_id,) if source_id is not None else (); matches=find_similar_faces(session, project_id, reference, scope, mode); best={}
    for face,score in matches:
        current=best.get(face.photo_id); candidate=(score,_face_quality(face)); current_rank=(current[1],_face_quality(current[0])) if current else None
        if current_rank is None or candidate > current_rank: best[face.photo_id]=(face,score)
    return sorted(best.values(), key=lambda item:(item[1],_face_quality(item[0])), reverse=True)


def _photo_matches_and_mode_counts(session, project_id, reference_face, source_id, active_mode):
    broad=_ordered_photo_matches(session,project_id,reference_face,source_id,"broad"); counts={name:sum(1 for _,score in broad if score>=threshold) for name,threshold in SEARCH_THRESHOLDS.items()}; threshold=SEARCH_THRESHOLDS[active_mode]
    return [(face,score) for face,score in broad if score>=threshold], counts


THUMB_SCRIPT='''<script>(function(){const waiting=new Set(Array.from(document.querySelectorAll('img.resilient-media[data-src]'))),queue=[];let active=0;const limit=4;function enqueue(img){if(!waiting.has(img))return;waiting.delete(img);queue.push(img);pump();}function pump(){while(active<limit&&queue.length){const img=queue.shift();active++;let attempt=0;const load=function(){attempt++;img.onload=function(){img.style.opacity='1';active--;pump();};img.onerror=function(){if(attempt<3)setTimeout(load,attempt*1200);else{img.onerror=null;img.alt='Preview temporarily unavailable';img.style.opacity='0.35';active--;pump();}};const joiner=img.dataset.src.indexOf('?')>=0?'&':'?';img.src=img.dataset.src+joiner+'attempt='+attempt+'&t='+Date.now();};load();}}if('IntersectionObserver'in window){const observer=new IntersectionObserver(function(entries){entries.forEach(function(entry){if(entry.isIntersecting){observer.unobserve(entry.target);enqueue(entry.target);}});},{rootMargin:'600px'});waiting.forEach(function(img){observer.observe(img);});}else Array.from(waiting).forEach(enqueue);})();</script>'''


def _resilient_img(src, alt, style, extra_class=""):
    return f'<img class="{("resilient-media "+extra_class).strip()}" data-src="{src}" alt="{escape(alt)}" style="{style};background:#e5e7eb;opacity:.92">'


@router.get("/{project_id}/faces/gallery", response_class=HTMLResponse)
def face_gallery(project_id:int, source_id:int|None=Query(None), dedup:str|None=Query(None), page_number:int=Query(1,alias="page",ge=1), session:Session=Depends(get_session), user:User=Depends(require_user)):
    project=session.get(Project,project_id)
    if not project: raise HTTPException(404,"Project not found")
    if dedup is None: dedup=get_app_settings(session).default_gallery_dedup
    sources=_project_sources(session,project_id); _validate_source(sources,source_id)
    if dedup not in DEDUP_THRESHOLDS: raise HTTPException(400,"Deduplication mode must be conservative, normal, or aggressive")
    threshold=DEDUP_THRESHOLDS[dedup]; conditions=[Face.project_id==project_id]
    if source_id is not None: conditions.append(Face.source_id==source_id)
    all_faces=session.scalars(select(Face).where(*conditions)).all(); all_faces.sort(key=lambda f:(_face_quality(f),f.detector_score or 0.0,f.id),reverse=True); representatives,suppressed=_representative_faces(all_faces,threshold); total=len(all_faces); representative_total=len(representatives); pages=max(1,math.ceil(representative_total/PAGE_SIZE)); page_number=min(page_number,pages); faces=representatives[(page_number-1)*PAGE_SIZE:page_number*PAGE_SIZE]; cards=[]; default_search=get_app_settings(session).default_search_mode
    for face in faces:
        photo=session.get(Photo,face.photo_id); source=session.get(PhotoSource,face.source_id)
        if not photo or not source: continue
        source_arg=f"&source_id={source_id}" if source_id is not None else ""; thumb=_resilient_img(f"/media/faces/{face.id}","Representative detected face","width:100%;height:230px;object-fit:cover;border-radius:12px")
        cards.append(f'<div class="card"><a title="Find similar photos" href="/projects/{project_id}/faces/{face.id}/matches?mode={default_search}{source_arg}">{thumb}</a><h3>{escape(photo.name)}</h3><p class="muted">Source: {escape(source.display_name or source.source_type)} · Quality: {_face_quality(face):.2f}</p><p><a class="button" href="/projects/{project_id}/faces/{face.id}/matches?mode={default_search}{source_arg}">Find Similar Photos</a></p><p><a class="button secondary" href="/media/photos/{photo.id}" target="_blank">View Photo</a> <a class="button secondary" href="/media/photos/{photo.id}/download">Download Original</a></p></div>')
    def page_link(number,label,active=False):
        source_arg=f"&source_id={source_id}" if source_id is not None else ""; cls="button" if active else "button secondary"; current=' aria-current="page"' if active else ""; return f'<a class="{cls}"{current} href="/projects/{project_id}/faces/gallery?page={number}&dedup={dedup}{source_arg}">{label}</a>'
    top_nav='<div class="row" style="justify-content:space-between;align-items:center">'+(page_link(page_number-1,"Previous") if page_number>1 else '<span></span>')+f'<span class="muted">Page {page_number} of {pages} · Clearest representative crops first</span>'+(page_link(page_number+1,"Next") if page_number<pages else '<span></span>')+'</div>'
    page_numbers=[]
    candidates={1,pages,page_number-2,page_number-1,page_number,page_number+1,page_number+2}; visible=sorted(n for n in candidates if 1<=n<=pages); previous=None
    for number in visible:
        if previous is not None and number-previous>1: page_numbers.append('<span class="muted" style="padding:8px 4px">…</span>')
        page_numbers.append(page_link(number,str(number),number==page_number)); previous=number
    bottom_nav='<nav aria-label="Gallery pages" style="margin-top:22px"><div class="row" style="justify-content:center;align-items:center;flex-wrap:wrap">'+(page_link(page_number-1,"Previous") if page_number>1 else '')+''.join(page_numbers)+(page_link(page_number+1,"Next") if page_number<pages else '')+'</div><p class="muted" style="text-align:center">Page '+str(page_number)+' of '+str(pages)+'</p></nav>'
    suppression=(suppressed/total*100.0) if total else 0.0
    body=f'<div class="row" style="justify-content:space-between"><div><h1>Representative Faces Gallery</h1><p class="muted">{total} indexed face region(s) · {representative_total} temporary representative(s) · {suppressed} similar crop(s) suppressed ({suppression:.1f}%). Dedup mode: {dedup.title()} · threshold {threshold:.2f}.</p><p class="muted">Thumbnails are loaded gradually to protect cloud sources from request bursts.</p></div><a class="button secondary" href="/ui/projects/{project_id}">Back to Project</a></div><div class="card"><form class="row" method="get"><select name="source_id">{_source_options(sources,source_id)}</select><select name="dedup">{_dedup_options(dedup)}</select><button type="submit">Apply Gallery Filter</button></form><p class="muted">Conservative keeps more representatives. Aggressive suppresses more visually similar crops.</p></div>{top_nav}<div class="grid">{"".join(cards) or EMPTY_GALLERY}</div>{bottom_nav}{THUMB_SCRIPT}'
    return page(f"{project.name} Faces",body,user=user)


@router.get("/{project_id}/faces/{face_id}/matches", response_class=HTMLResponse)
def face_matches(project_id:int, face_id:int, source_id:int|None=Query(None), mode:str|None=Query(None), session:Session=Depends(get_session), user:User=Depends(require_user)):
    project=session.get(Project,project_id); reference=session.get(Face,face_id)
    if not project: raise HTTPException(404,"Project not found")
    if not reference or reference.project_id!=project_id: raise HTTPException(404,"Face not found")
    if mode is None: mode=get_app_settings(session).default_search_mode
    sources=_project_sources(session,project_id); _validate_source(sources,source_id)
    if mode not in SEARCH_THRESHOLDS: raise HTTPException(400,"Search mode must be strict, recommended, balanced, or broad")
    ordered,counts=_photo_matches_and_mode_counts(session,project_id,reference,source_id,mode); cards=[]
    for rank,(face,score) in enumerate(ordered,start=1):
        photo=session.get(Photo,face.photo_id); source=session.get(PhotoSource,face.source_id)
        if not photo or not source: continue
        crop=_resilient_img(f"/media/faces/{face.id}","Matched face crop","width:110px;height:110px;object-fit:cover;border-radius:12px"); preview=_resilient_img(f"/media/photos/{photo.id}",photo.name,"width:100%;height:260px;object-fit:cover;border-radius:12px;margin-top:10px"); margin=score-SEARCH_THRESHOLDS[mode]
        cards.append(f'<div class="card"><div class="row" style="align-items:flex-start">{crop}<div><strong>Result #{rank}</strong><p class="muted">Similarity: {score:.3f}<br>Threshold: {SEARCH_THRESHOLDS[mode]:.2f}<br>Margin: +{margin:.3f}<br>Crop quality: {_face_quality(face):.2f}</p></div></div>{preview}<h3>{escape(photo.name)}</h3><p class="muted">Source: {escape(source.display_name or source.source_type)}</p><p><a class="button" href="/media/photos/{photo.id}" target="_blank">View Photo</a> <a class="button secondary" href="/media/photos/{photo.id}/download">Download Original</a></p></div>')
    source_arg=f"&source_id={source_id}" if source_id is not None else ""; links=[]
    for name in ("strict","recommended","balanced","broad"):
        links.append(f'<a class="{"button" if name==mode else "button secondary"}" href="/projects/{project_id}/faces/{face_id}/matches?mode={name}{source_arg}">{name.title()} ({SEARCH_THRESHOLDS[name]:.2f}) — {counts[name]} photo(s)</a>')
    download=f'/projects/{project_id}/faces/{face_id}/matches/download?mode={mode}{source_arg}'
    if ordered:
        bulk=(f'<a id="bulk-download" class="button" style="width:100%;text-align:center" href="{download}" '
              f'onclick="if(this.dataset.busy)return false;this.dataset.busy=\'1\';this.textContent=\'Preparing {len(ordered)} originals... Please wait\';this.style.opacity=\'0.65\';document.getElementById(\'bulk-status\').style.display=\'block\';return true;">'
              f'Download All {len(ordered)} Originals (.zip)</a>'
              f'<span id="bulk-status" class="muted" style="display:none;margin-top:8px">Retrieving originals and building the ZIP. The download will start automatically.</span>')
    else:
        bulk=""
    scores=[score for _,score in ordered]; summary=(f'Highest {max(scores):.3f} · Lowest {min(scores):.3f} · Active threshold {SEARCH_THRESHOLDS[mode]:.2f}' if scores else f'No results at active threshold {SEARCH_THRESHOLDS[mode]:.2f}'); reference_img=_resilient_img(f"/media/faces/{face_id}","Selected face","width:150px;height:150px;object-fit:cover;border-radius:12px"); back=f"?source_id={source_id}" if source_id is not None else ""
    body=f'<div class="row" style="justify-content:space-between"><div><h1>Similar Photo Search</h1><p class="muted">Using the selected detected face as a temporary reference. Similarity is a ranking signal, not an identity probability.</p></div><a class="button secondary" href="/projects/{project_id}/faces/gallery{back}">Back to Faces</a></div><div class="card"><div class="split-panel" style="grid-template-columns:minmax(0,1fr) minmax(330px,430px);align-items:start"><div class="row" style="align-items:flex-start;flex-wrap:nowrap">{reference_img}<div><h3>Selected reference face</h3><p>{len(ordered)} photo result(s)<br><span class="muted">{summary}</span></p></div></div><div class="action-list" style="margin-left:auto">{"".join(links)}<div style="margin-top:7px">{bulk}</div></div></div></div><div class="grid">{"".join(cards) or EMPTY_MATCHES}</div>{THUMB_SCRIPT}'
    return page(f"{project.name} Similar Photos",body,user=user)