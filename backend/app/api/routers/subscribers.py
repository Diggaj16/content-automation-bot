"""
Email subscriber management.

GET    /subscribers          — list all subscribers, optional ?active=true/false
POST   /subscribers          — add subscriber; 409 if email already exists
PATCH  /subscribers/{id}     — update name and/or active status
DELETE /subscribers/{id}     — soft-delete (sets active=false)
GET    /unsubscribe           — public token-based unsubscribe (no auth)
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from supabase import Client

from app.api.deps import get_supabase

router = APIRouter(tags=["Subscribers"])


class SubscriberCreate(BaseModel):
    email: str
    name: Optional[str] = None


class SubscriberUpdate(BaseModel):
    name: Optional[str] = None
    active: Optional[bool] = None


@router.get("/subscribers")
def list_subscribers(
    active: Optional[bool] = Query(None),
    supabase: Client = Depends(get_supabase),
) -> list[dict]:
    try:
        q = supabase.table("email_subscribers").select("*")
        if active is not None:
            q = q.eq("active", active)
        resp = q.execute()
        return resp.data or []
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/subscribers", status_code=201)
def add_subscriber(
    body: SubscriberCreate,
    supabase: Client = Depends(get_supabase),
) -> dict:
    # Check for duplicate
    try:
        existing = (
            supabase.table("email_subscribers")
            .select("id")
            .eq("email", body.email)
            .execute()
        )
        if existing.data:
            raise HTTPException(status_code=409, detail="Email already subscribed")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    try:
        payload: dict = {
            "email": body.email,
            "unsubscribe_token": str(uuid.uuid4()),
        }
        if body.name:
            payload["name"] = body.name
        resp = supabase.table("email_subscribers").insert(payload).execute()
        if not resp.data:
            raise HTTPException(status_code=500, detail="Insert returned no data")
        return resp.data[0]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/subscribers/{sub_id}")
def update_subscriber(
    sub_id: str,
    body: SubscriberUpdate,
    supabase: Client = Depends(get_supabase),
) -> dict:
    update: dict = {}
    if body.name is not None:
        update["name"] = body.name
    if body.active is not None:
        update["active"] = body.active
    if not update:
        raise HTTPException(status_code=422, detail="Nothing to update")
    try:
        resp = (
            supabase.table("email_subscribers")
            .update(update)
            .eq("id", sub_id)
            .execute()
        )
        if not resp.data:
            raise HTTPException(status_code=404, detail="Subscriber not found")
        return resp.data[0]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/subscribers/{sub_id}")
def delete_subscriber(
    sub_id: str,
    supabase: Client = Depends(get_supabase),
) -> dict:
    try:
        resp = (
            supabase.table("email_subscribers")
            .update({"active": False})
            .eq("id", sub_id)
            .execute()
        )
        if not resp.data:
            raise HTTPException(status_code=404, detail="Subscriber not found")
        return {"deleted": True, "id": sub_id}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/unsubscribe", response_class=HTMLResponse)
def unsubscribe(
    token: str = Query(...),
    supabase: Client = Depends(get_supabase),
) -> HTMLResponse:
    try:
        resp = (
            supabase.table("email_subscribers")
            .select("id, email")
            .eq("unsubscribe_token", token)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if not resp.data:
        return HTMLResponse(
            content=_html("Not Found", "This unsubscribe link is invalid or has already been used."),
            status_code=404,
        )

    sub = resp.data[0]
    try:
        supabase.table("email_subscribers").update({"active": False}).eq("id", sub["id"]).execute()
    except Exception:
        pass

    return HTMLResponse(
        content=_html(
            "Unsubscribed",
            f"<strong>{sub['email']}</strong> has been unsubscribed from all future emails.",
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
