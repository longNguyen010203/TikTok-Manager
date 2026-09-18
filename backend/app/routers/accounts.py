"""Account CRUD endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Account
from app.schemas.account import (
    AccountCreate,
    AccountList,
    AccountRead,
    AccountUpdate,
)

router = APIRouter(prefix="/accounts", tags=["accounts"])
DatabaseSession = Annotated[Session, Depends(get_db)]


def _get_account_or_404(account_id: int, session: Session) -> Account:
    account = session.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.get("", response_model=AccountList)
def list_accounts(
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    account_status: Annotated[
        str | None, Query(alias="status", min_length=1)
    ] = None,
) -> AccountList:
    """List accounts using page-based pagination and optional status filtering."""
    filters = []
    if account_status is not None:
        filters.append(Account.status == account_status)

    total = session.scalar(select(func.count()).select_from(Account).where(*filters))
    accounts = session.scalars(
        select(Account)
        .where(*filters)
        .order_by(Account.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return AccountList(
        items=list(accounts),
        total=total or 0,
        page=page,
        page_size=page_size,
    )


@router.get("/{account_id}", response_model=AccountRead)
def get_account(account_id: int, session: DatabaseSession) -> Account:
    """Return one account by ID."""
    return _get_account_or_404(account_id, session)


@router.post("", response_model=AccountRead, status_code=status.HTTP_201_CREATED)
def create_account(payload: AccountCreate, session: DatabaseSession) -> Account:
    """Create an account."""
    account = Account(**payload.model_dump())
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


@router.patch("/{account_id}", response_model=AccountRead)
def update_account(
    account_id: int, payload: AccountUpdate, session: DatabaseSession
) -> Account:
    """Update fields supplied for an account."""
    account = _get_account_or_404(account_id, session)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(account, field, value)

    session.commit()
    session.refresh(account)
    return account


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(account_id: int, session: DatabaseSession) -> Response:
    """Delete an account."""
    account = _get_account_or_404(account_id, session)
    session.delete(account)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
