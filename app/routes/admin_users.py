from html import escape

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.database import get_session
from app.models import LoginSession, User
from app.security import hash_password
from app.ui import page

router = APIRouter(prefix="/ui/users", tags=["admin-users"])


def _active_admin_count(session: Session) -> int:
    return session.scalar(select(func.count(User.id)).where(User.role == "admin", User.active.is_(True))) or 0


def _get_user(session: Session, user_id: int) -> User:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    return user


@router.get("", response_class=HTMLResponse)
def users_page(session: Session = Depends(get_session), admin: User = Depends(require_admin)):
    users = session.scalars(select(User).order_by(User.created_at, User.id)).all()
    rows = []
    for user in users:
        status = "Active" if user.active else "Disabled"
        action = "Disable" if user.active else "Enable"
        self_note = ' <span class="muted">(you)</span>' if user.id == admin.id else ""
        rows.append(f'''<tr><td><strong>{escape(user.display_name or user.username)}</strong>{self_note}<br><span class="muted">{escape(user.username)}</span></td><td>{escape(user.role.title())}</td><td>{status}</td><td>{user.last_login_at.strftime("%Y-%m-%d %H:%M") if user.last_login_at else "Never"}</td><td><div class="row"><form action="/ui/users/{user.id}/toggle" method="post"><button class="secondary" type="submit">{action}</button></form><form class="row" action="/ui/users/{user.id}/password" method="post"><input name="password" type="password" minlength="10" placeholder="New password" required><button type="submit">Reset Password</button></form></div></td></tr>''')
    body = f'''<div class="row" style="justify-content:space-between"><div><h1>User Management</h1><p class="muted">Create administrators and ordinary users, control access, and reset local passwords.</p></div></div>
<div class="card"><h2>Create User</h2><form class="row" action="/ui/users" method="post"><input name="display_name" placeholder="Display name"><input name="username" placeholder="Username" maxlength="120" required><input name="password" type="password" minlength="10" placeholder="Temporary password (10+ chars)" required><select name="role"><option value="user" selected>Ordinary User</option><option value="admin">Administrator</option></select><button type="submit">Create User</button></form><p class="muted">Passwords are stored only as Argon2 hashes. Multiple administrators are supported.</p></div>
<div class="card"><table><thead><tr><th>User</th><th>Role</th><th>Status</th><th>Last login</th><th>Administration</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>'''
    return page("User Management", body, user=admin)


@router.post("")
def create_user(display_name: str = Form(""), username: str = Form(...), password: str = Form(...), role: str = Form("user"), session: Session = Depends(get_session), _: User = Depends(require_admin)):
    username = username.strip().lower()
    if not username or len(username) > 120:
        raise HTTPException(400, "Username is required and must be at most 120 characters")
    if role not in {"admin", "user"}:
        raise HTTPException(400, "Role must be admin or user")
    if session.scalar(select(User).where(func.lower(User.username) == username)):
        raise HTTPException(409, "Username already exists")
    try:
        password_hash = hash_password(password)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    session.add(User(username=username, display_name=display_name.strip() or None, password_hash=password_hash, role=role, active=True))
    session.commit()
    return RedirectResponse("/ui/users", status_code=303)


@router.post("/{user_id}/toggle")
def toggle_user(user_id: int, session: Session = Depends(get_session), admin: User = Depends(require_admin)):
    target = _get_user(session, user_id)
    if target.active and target.role == "admin" and _active_admin_count(session) <= 1:
        raise HTTPException(409, "The last active administrator cannot be disabled")
    if target.id == admin.id and target.active:
        raise HTTPException(409, "You cannot disable your own signed-in administrator account")
    target.active = not target.active
    if not target.active:
        for login in session.scalars(select(LoginSession).where(LoginSession.user_id == target.id)).all():
            session.delete(login)
    session.commit()
    return RedirectResponse("/ui/users", status_code=303)


@router.post("/{user_id}/password")
def reset_password(user_id: int, password: str = Form(...), session: Session = Depends(get_session), _: User = Depends(require_admin)):
    target = _get_user(session, user_id)
    try:
        target.password_hash = hash_password(password)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    for login in session.scalars(select(LoginSession).where(LoginSession.user_id == target.id)).all():
        session.delete(login)
    session.commit()
    return RedirectResponse("/ui/users", status_code=303)
