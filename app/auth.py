from datetime import datetime

from fastapi import Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import LoginSession, User
from app.security import token_digest

SESSION_COOKIE = "auroara_fpf_session"


def has_users(session: Session) -> bool:
    return bool(session.scalar(select(func.count(User.id))))


def current_user_optional(request: Request, session: Session = Depends(get_session)) -> User | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    login = session.scalar(select(LoginSession).where(LoginSession.token_digest == token_digest(token)))
    if not login or login.expires_at <= datetime.utcnow():
        if login:
            session.delete(login)
            session.commit()
        return None
    user = session.get(User, login.user_id)
    return user if user and user.active else None


def require_user(user: User | None = Depends(current_user_optional)) -> User:
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_admin(user: User = Depends(require_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required")
    return user
