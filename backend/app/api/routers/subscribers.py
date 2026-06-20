"""
Email subscriber management.

GET    /subscribers          — list all subscribers, optional ?active=true/false
POST   /subscribers          — add subscriber; 409 if email already exists
PATCH  /subscribers/{id}     — update name and/or active status
DELETE /subscribers/{id}     — soft-delete (sets active=false)
GET    /unsubscribe           — public token-based unsubscribe (no auth)
"""
import html as _html_module
import re
import uuid
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.orm import EmailSubscriber
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["Subscribers"])


class SubscriberCreate(BaseModel):
    email: str
    name: Optional[str] = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
            raise ValueError("Invalid email address")
        return v


class SubscriberUpdate(BaseModel):
    name: Optional[str] = None
    active: Optional[bool] = None


def _sub_to_dict(sub: EmailSubscriber, include_token: bool = False) -> dict:
    d = {
        "id": str(sub.id),
        "email": sub.email,
        "name": sub.name,
        "subscribed_date": sub.subscribed_date,
        "source": sub.source,
        "active": sub.active,
        "created_at": sub.created_at,
    }
    if include_token:
        d["unsubscribe_token"] = sub.unsubscribe_token
    return d


@router.get("/subscribers")
def list_subscribers(
    active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
) -> list[dict]:
    try:
        stmt = select(EmailSubscriber)
        if active is not None:
            stmt = stmt.where(EmailSubscriber.active == active)
        rows = db.execute(stmt).scalars().all()
        return [_sub_to_dict(r) for r in rows]
    except Exception as exc:
        logger.warning("list_subscribers failed", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/subscribers", status_code=201)
def add_subscriber(
    body: SubscriberCreate,
    db: Session = Depends(get_db),
) -> dict:
    # Check for duplicate
    try:
        existing = db.execute(
            select(EmailSubscriber.id).where(EmailSubscriber.email == body.email)
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="Email already subscribed")
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("add_subscriber: duplicate check failed", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Internal server error")

    try:
        row = EmailSubscriber(
            email=body.email,
            name=body.name or None,
            unsubscribe_token=str(uuid.uuid4()),
        )
        db.add(row)
        db.commit()
        return _sub_to_dict(row)
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.warning("add_subscriber: insert failed", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/subscribers/{sub_id}")
def update_subscriber(
    sub_id: UUID,
    body: SubscriberUpdate,
    db: Session = Depends(get_db),
) -> dict:
    if body.name is None and body.active is None:
        raise HTTPException(status_code=422, detail="Nothing to update")
    try:
        sub = db.get(EmailSubscriber, sub_id)
        if sub is None:
            raise HTTPException(status_code=404, detail="Subscriber not found")
        if body.name is not None:
            sub.name = body.name
        if body.active is not None:
            sub.active = body.active
        db.commit()
        return _sub_to_dict(sub)
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.warning("update_subscriber failed", extra={"sub_id": str(sub_id), "error": str(exc)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/subscribers/{sub_id}")
def delete_subscriber(
    sub_id: UUID,
    db: Session = Depends(get_db),
) -> dict:
    try:
        sub = db.get(EmailSubscriber, sub_id)
        if sub is None:
            raise HTTPException(status_code=404, detail="Subscriber not found")
        sub.active = False
        db.commit()
        return {"deleted": True, "id": str(sub_id)}
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.warning("delete_subscriber failed", extra={"sub_id": str(sub_id), "error": str(exc)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/unsubscribe", response_class=HTMLResponse)
def unsubscribe(
    token: str = Query(...),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    try:
        sub = db.execute(
            select(EmailSubscriber).where(EmailSubscriber.unsubscribe_token == token)
        ).scalar_one_or_none()
    except Exception as exc:
        logger.warning("unsubscribe: lookup failed", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Internal server error")

    if sub is None:
        return HTMLResponse(
            content=_html("Not Found", "This unsubscribe link is invalid or has already been used."),
            status_code=404,
        )

    try:
        sub.active = False
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("unsubscribe: failed to deactivate subscriber", extra={"error": str(exc), "id": str(sub.id)})

    return HTMLResponse(
        content=_html(
            "Unsubscribed",
            f"<strong>{_html_module.escape(sub.email)}</strong> has been unsubscribed from all future emails.",
        ),
        status_code=200,
    )


def _html(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>{title}</title>
<style>body{{font-family:system-ui,sans-serif;max-width:480px;margin:80px auto;text-align:center;color:#1f2937}}
h1{{font-size:1.5rem;font-weight:600}}p{{color:#6b7280;margin-top:.75rem}}</style>
</head>
<body><h1>{title}</h1><p>{body}</p></body>
</html>"""
