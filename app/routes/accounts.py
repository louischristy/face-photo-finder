from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.database import get_session
from app.models import StorageAccount, User
from app.services.google_accounts import connect_google_account

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("")
def list_accounts(session: Session = Depends(get_session), _: User = Depends(require_admin)):
    accounts = session.scalars(select(StorageAccount).order_by(StorageAccount.created_at.desc())).all()
    return [
        {"id": a.id, "provider": a.provider, "label": a.label, "account": a.account_hint, "active": a.active}
        for a in accounts
    ]


@router.post("/google")
def add_google_account(label: str = Form("Google Drive"), session: Session = Depends(get_session), _: User = Depends(require_admin)):
    try:
        account = connect_google_account(session, label)
    except FileNotFoundError as exc:
        raise HTTPException(400, str(exc)) from exc
    return RedirectResponse(f"/ui/accounts?connected={account.id}", status_code=303)
