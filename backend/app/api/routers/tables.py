"""
Generic DB table browser — exposes all 15 tables for the admin frontend.

GET  /tables                       — list available tables
GET  /tables/{table_name}          — list rows with optional filters
GET  /tables/{table_name}/{row_id} — get a single row by id
POST /tables/{table_name}          — insert a row
PATCH /tables/{table_name}/{row_id} — update a row
DELETE /tables/{table_name}/{row_id} — delete a row
"""
import uuid as _uuid
from typing import Optional, Type

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.base import Base
from app.db.orm import (
    BrandMemory,
    ContentAnalytics,
    CostLog,
    CuratedSite,
    Draft,
    EmailSubscriber,
    Idea,
    KnowledgeBase,
    PublishedPost,
    RawContent,
    RunLog,
    SiteHealthLog,
    StyleGuide,
    TopicPerformanceModel,
    UserDecisionSummary,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)

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

_TABLE_MODELS: dict[str, Type[Base]] = {
    "curated_sites": CuratedSite,
    "raw_content": RawContent,
    "ideas": Idea,
    "user_decision_summaries": UserDecisionSummary,
    "drafts": Draft,
    "published_posts": PublishedPost,
    "content_analytics": ContentAnalytics,
    "email_subscribers": EmailSubscriber,
    "style_guide": StyleGuide,
    "topic_performance_model": TopicPerformanceModel,
    "brand_memory": BrandMemory,
    "knowledge_base": KnowledgeBase,
    "run_logs": RunLog,
    "site_health_log": SiteHealthLog,
    "cost_log": CostLog,
}

# Tables that sort by updated_at instead of created_at
_TABLE_SORT_COLUMN: dict[str, str] = {
    "style_guide": "updated_at",
    "topic_performance_model": "updated_at",
}

# For these tables, enrich rows with a joined lookup to show human-readable context.
# key = table_name, value = (fk_column, lookup_table, lookup_id_col, display_cols)
# NOTE: "raw_content_id" does not exist on `ideas` (the real FK is
# source_article_id) — this enrichment was already a no-op under Supabase
# (row.get("raw_content_id") was always None) and is kept as-is here rather
# than silently "fixed" as part of an unrelated DB migration.
_ROW_ENRICHMENTS: dict[str, tuple[str, str, str, list[str]]] = {
    "ideas": ("raw_content_id", "raw_content", "id", ["title", "source_name"]),
}

VECTOR_COLUMNS = {"brand_memory": "embedding", "knowledge_base": "embedding"}


def _validate_table(table_name: str) -> Type[Base]:
    model = _TABLE_MODELS.get(table_name)
    if model is None:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")
    return model


def _row_to_dict(model: Type[Base], row, exclude: Optional[str] = None) -> dict:
    return {
        c.name: getattr(row, c.name)
        for c in model.__table__.columns
        if c.name != exclude
    }


def _coerce_filter_value(model: Type[Base], column_name: str, raw_value: str):
    """Best-effort coercion of a query-string filter value to the column's Python type."""
    column = model.__table__.columns.get(column_name)
    if column is None:
        return raw_value
    py_type = column.type.python_type
    try:
        if py_type is bool:
            return raw_value.lower() in ("true", "1", "yes")
        if py_type is int:
            return int(raw_value)
        if py_type is float:
            return float(raw_value)
        if py_type is _uuid.UUID:
            return _uuid.UUID(raw_value)
        return raw_value
    except (ValueError, TypeError):
        return raw_value


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
    db: Session = Depends(get_db),
) -> dict:
    model = _validate_table(table_name)
    # Substitute the correct sort column when caller uses the generic default
    default_sort = _TABLE_SORT_COLUMN.get(table_name, "created_at")
    effective_order_by = default_sort if order_by == "created_at" and table_name in _TABLE_SORT_COLUMN else order_by
    try:
        exclude_col = VECTOR_COLUMNS.get(table_name)

        count_stmt = select(func.count()).select_from(model)
        query = select(model)

        if filter_column and filter_value is not None:
            value = _coerce_filter_value(model, filter_column, filter_value)
            col = getattr(model, filter_column)
            count_stmt = count_stmt.where(col == value)
            query = query.where(col == value)

        order_col = getattr(model, effective_order_by)
        query = query.order_by(order_col.desc() if order_desc else order_col.asc())
        query = query.offset(offset).limit(limit)

        total = db.execute(count_stmt).scalar_one()
        rows_orm = db.execute(query).scalars().all()
        rows = [_row_to_dict(model, r, exclude=exclude_col) for r in rows_orm]

        # Enrich rows with human-readable context from related tables
        enrichment = _ROW_ENRICHMENTS.get(table_name)
        if enrichment and rows:
            fk_col, lookup_table, lookup_id_col, display_cols = enrichment
            fk_ids = list({row[fk_col] for row in rows if row.get(fk_col)})
            if fk_ids:
                try:
                    lookup_model = _TABLE_MODELS[lookup_table]
                    lookup_id_attr = getattr(lookup_model, lookup_id_col)
                    lookup_rows = db.execute(
                        select(lookup_model).where(lookup_id_attr.in_(fk_ids))
                    ).scalars().all()
                    lookup_map: dict = {
                        getattr(r, lookup_id_col): {c: getattr(r, c) for c in display_cols}
                        for r in lookup_rows
                    }
                    for row in rows:
                        fk_val = row.get(fk_col)
                        if fk_val and fk_val in lookup_map:
                            for col, val in lookup_map[fk_val].items():
                                row[f"_src_{col}"] = val
                except Exception:
                    pass  # enrichment is best-effort; never fail the main request

        columns = list(rows[0].keys()) if rows else []

        return {
            "table": table_name,
            "rows": rows,
            "count": total,
            "limit": limit,
            "offset": offset,
            "columns": columns,
            "default_sort": default_sort,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("tables router error", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{table_name}/{row_id}")
def get_row(
    table_name: str,
    row_id: str,
    db: Session = Depends(get_db),
) -> dict:
    model = _validate_table(table_name)
    try:
        row = db.get(model, _uuid.UUID(row_id))
        if row is None:
            raise HTTPException(status_code=404, detail="Row not found")

        exclude_col = VECTOR_COLUMNS.get(table_name)
        return _row_to_dict(model, row, exclude=exclude_col)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("tables router error", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{table_name}")
def insert_row(
    table_name: str,
    payload: dict,
    db: Session = Depends(get_db),
) -> dict:
    model = _validate_table(table_name)
    payload.pop("id", None)
    payload.pop("created_at", None)
    payload.pop("updated_at", None)
    try:
        valid_cols = set(model.__table__.columns.keys())
        clean_payload = {k: v for k, v in payload.items() if k in valid_cols}
        row = model(**clean_payload)
        db.add(row)
        db.commit()
        return _row_to_dict(model, row)
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.warning("tables router error", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{table_name}/{row_id}")
def update_row(
    table_name: str,
    row_id: str,
    payload: dict,
    db: Session = Depends(get_db),
) -> dict:
    model = _validate_table(table_name)
    payload.pop("id", None)
    payload.pop("created_at", None)
    try:
        row = db.get(model, _uuid.UUID(row_id))
        if row is None:
            raise HTTPException(status_code=404, detail="Row not found")

        valid_cols = set(model.__table__.columns.keys())
        for k, v in payload.items():
            if k in valid_cols:
                setattr(row, k, v)
        db.commit()
        return _row_to_dict(model, row)
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.warning("tables router error", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{table_name}/{row_id}")
def delete_row(
    table_name: str,
    row_id: str,
    db: Session = Depends(get_db),
) -> dict:
    model = _validate_table(table_name)
    try:
        row = db.get(model, _uuid.UUID(row_id))
        if row is not None:
            db.delete(row)
            db.commit()
        return {"deleted": True, "id": row_id}
    except Exception as exc:
        db.rollback()
        logger.warning("tables router error", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Internal server error")
