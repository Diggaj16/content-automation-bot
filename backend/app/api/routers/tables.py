"""
Generic DB table browser — exposes all 15 tables for the admin frontend.

GET  /tables                       — list available tables
GET  /tables/{table_name}          — list rows with optional filters
GET  /tables/{table_name}/{row_id} — get a single row by id
POST /tables/{table_name}          — insert a row
PATCH /tables/{table_name}/{row_id} — update a row
DELETE /tables/{table_name}/{row_id} — delete a row
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from app.api.deps import get_supabase

router = APIRouter(prefix="/tables", tags=["DB Browser"])

ALLOWED_TABLES = [
    "curated_sites",
    "raw_content",
    "ideas",
    "user_decision_summaries",
    "drafts",
    "published_posts",
    "content_analytics",
    "email_subscribers",
    "style_guide",
    "topic_performance_model",
    "brand_memory",
    "knowledge_base",
    "run_logs",
    "site_health_log",
    "cost_log",
]

# Tables that sort by updated_at instead of created_at
_TABLE_SORT_COLUMN: dict[str, str] = {
    "style_guide": "updated_at",
    "topic_performance_model": "updated_at",
}

VECTOR_COLUMNS = {"brand_memory": "embedding", "knowledge_base": "embedding"}


def _select_columns(table_name: str) -> str:
    col = VECTOR_COLUMNS.get(table_name)
    if col:
        return f"*, !inner({col})"
    return "*"


def _validate_table(table_name: str) -> None:
    if table_name not in ALLOWED_TABLES:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")


@router.get("")
def list_tables() -> list[str]:
    return ALLOWED_TABLES


@router.get("/{table_name}")
def list_rows(
    table_name: str,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    order_by: str = Query(default="created_at"),
    order_desc: bool = Query(default=True),
    filter_column: Optional[str] = Query(default=None),
    filter_value: Optional[str] = Query(default=None),
    supabase: Client = Depends(get_supabase),
) -> dict:
    _validate_table(table_name)
    # Substitute the correct sort column when caller uses the generic default
    default_sort = _TABLE_SORT_COLUMN.get(table_name, "created_at")
    effective_order_by = default_sort if order_by == "created_at" and table_name in _TABLE_SORT_COLUMN else order_by
    try:
        exclude_col = VECTOR_COLUMNS.get(table_name)
        query = supabase.table(table_name).select("*", count="exact")

        if filter_column and filter_value is not None:
            query = query.eq(filter_column, filter_value)

        query = query.order(effective_order_by, desc=order_desc)
        query = query.range(offset, offset + limit - 1)

        resp = query.execute()
        rows = resp.data or []

        if exclude_col:
            for row in rows:
                row.pop(exclude_col, None)

        columns = list(rows[0].keys()) if rows else []

        return {
            "table": table_name,
            "rows": rows,
            "count": resp.count,
            "limit": limit,
            "offset": offset,
            "columns": columns,
            "default_sort": default_sort,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{table_name}/{row_id}")
def get_row(
    table_name: str,
    row_id: str,
    supabase: Client = Depends(get_supabase),
) -> dict:
    _validate_table(table_name)
    try:
        id_col = "id"
        resp = (
            supabase.table(table_name)
            .select("*")
            .eq(id_col, row_id)
            .limit(1)
            .execute()
        )
        if not resp.data:
            raise HTTPException(status_code=404, detail="Row not found")

        row = resp.data[0]
        exclude_col = VECTOR_COLUMNS.get(table_name)
        if exclude_col:
            row.pop(exclude_col, None)

        return row
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{table_name}")
def insert_row(
    table_name: str,
    payload: dict,
    supabase: Client = Depends(get_supabase),
) -> dict:
    _validate_table(table_name)
    payload.pop("id", None)
    payload.pop("created_at", None)
    payload.pop("updated_at", None)
    try:
        resp = supabase.table(table_name).insert(payload).execute()
        if not resp.data:
            raise HTTPException(status_code=500, detail="Insert returned no data")
        return resp.data[0]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/{table_name}/{row_id}")
def update_row(
    table_name: str,
    row_id: str,
    payload: dict,
    supabase: Client = Depends(get_supabase),
) -> dict:
    _validate_table(table_name)
    payload.pop("id", None)
    payload.pop("created_at", None)
    try:
        resp = (
            supabase.table(table_name)
            .update(payload)
            .eq("id", row_id)
            .execute()
        )
        if not resp.data:
            raise HTTPException(status_code=404, detail="Row not found")
        return resp.data[0]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/{table_name}/{row_id}")
def delete_row(
    table_name: str,
    row_id: str,
    supabase: Client = Depends(get_supabase),
) -> dict:
    _validate_table(table_name)
    try:
        resp = (
            supabase.table(table_name)
            .delete()
            .eq("id", row_id)
            .execute()
        )
        return {"deleted": True, "id": row_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
