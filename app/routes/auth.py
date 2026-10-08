from datetime import datetime
from html import escape

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.auth import SESSION_COOKIE, current_user_optional
from app.branding import APP_NAME
from app.database import get_session
from app.login_throttle import clear_failures, is_blocked, record_failure
from app.models import LoginSession, User
from app.security import hash_password, new_session_token, session_expiry, token_digest, verify_password
from app.ui import page

router = APIRouter(tags=["auth"])


def _auth_card(title: str, intro: str, form_html: str, error: str | None = None) -> str:
    error_html = f'<div class="card" style="border-color:#dc2626;color:#991b1b">{escape(error)}</div>' if error else ""
    return page(title, f'<div style="max-width:520px;margin:55px auto">{error_html}<div class="card"><h1>{escape(title)}</h1><p class="muted">{escape(intro)}</p>{form_html}</div></div>', show_nav=False)


def _login_form() -> str:
    return '''<form method="post" action="/login" class="stack"><label>Username<input name="username" autocomplete="username" autofocus required></label><label>Password<input type="password" name="password" autocomplete="current-password" required></label><button type="submit">Sign In</button></form>'''


@router.get("/setup", response_class=HTMLResponse)
def setup_page(session: Session = Depends(get_session)):
    if session.scalar(select(func.count(User.id))): return RedirectResponse("/login", status_code=303)
    form='''<form method="post" action="/setup" class="stack"><label>Administrator name<input name="display_name" autocomplete="name" required></label><label>Username<input name="username" autocomplete="username" required></label><label>Password<input type="password" name="password" autocomplete="new-password" minlength="10" required></label><label>Confirm password<input type="password" name="confirm_password" autocomplete="new-password" minlength="10" required></label><button type="submit">Create Administrator</button></form>'''
    return _auth_card("First-run setup",f"Create the first administrator for {APP_NAME}. This account controls system settings and other users.",form)


@router.post("/setup")
def setup_admin(display_name:str=Form(...),username:str=Form(...),password:str=Form(...),confirm_password:str=Form(...),session:Session=Depends(get_session)):
    if session.scalar(select(func.count(User.id))): raise HTTPException(409,"Initial administrator already exists")
    username=username.strip().lower()
    if not username or len(username)>120: raise HTTPException(400,"Invalid username")
    if password!=confirm_password: raise HTTPException(400,"Passwords do not match")
    try: password_hash=hash_password(password)
    except ValueError as exc: raise HTTPException(400,str(exc)) from exc
    session.add(User(username=username,display_name=display_name.strip()[:200] or username,password_hash=password_hash,role="admin",active=True));session.commit();return RedirectResponse("/login?created=1",status_code=303)


@router.get("/login",response_class=HTMLResponse)
def login_page(request:Request,session:Session=Depends(get_session),user:User|None=Depends(current_user_optional)):
    if not session.scalar(select(func.count(User.id))): return RedirectResponse("/setup",status_code=303)
    if user: return RedirectResponse("/ui/projects",status_code=303)
    created=request.query_params.get("created")=="1";intro="Administrator created. Sign in to continue." if created else "Sign in to access the local photo-search workspace."
    return _auth_card("Sign in",intro,_login_form())


@router.post("/login")
def login(request:Request,username:str=Form(...),password:str=Form(...),session:Session=Depends(get_session)):
    normalized=username.strip().lower();client=request.client.host if request.client else "local"
    if is_blocked(normalized,client):
        return HTMLResponse(_auth_card("Sign in","Sign in to access the local photo-search workspace.",_login_form(),"Too many failed attempts. Try again in a few minutes."),status_code=429,headers={"Retry-After":"300"})
    user=session.scalar(select(User).where(User.username==normalized))
    if not user or not user.active or not verify_password(user.password_hash,password):
        record_failure(normalized,client)
        return HTMLResponse(_auth_card("Sign in","Sign in to access the local photo-search workspace.",_login_form(),"Invalid username or password."),status_code=401)
    clear_failures(normalized,client);session.execute(delete(LoginSession).where(LoginSession.expires_at<=datetime.utcnow()));raw_token=new_session_token();session.add(LoginSession(user_id=user.id,token_digest=token_digest(raw_token),expires_at=session_expiry().replace(tzinfo=None)));user.last_login_at=datetime.utcnow();session.commit();response=RedirectResponse("/ui/projects",status_code=303);response.set_cookie(SESSION_COOKIE,raw_token,max_age=12*60*60,httponly=True,samesite="strict",secure=False,path="/");return response


@router.post("/logout")
def logout(request:Request,session:Session=Depends(get_session)):
    token=request.cookies.get(SESSION_COOKIE)
    if token: session.execute(delete(LoginSession).where(LoginSession.token_digest==token_digest(token)));session.commit()
    response=RedirectResponse("/login",status_code=303);response.delete_cookie(SESSION_COOKIE,path="/");return response
