"""
Mock Supabase client for testing.

Provides a FakeSupabaseClient that mimics the Supabase query builder API
with in-memory dicts. Supports select, insert, update, eq, order, limit,
range, count, in_, execute, and rpc.
"""
from __future__ import annotations

import copy
import re
from datetime import datetime
from typing import Any, Callable, Optional
from uuid import uuid4


class FakeQueryResponse:
    """Mimics the supabase-py response object."""

    def __init__(
        self,
        data: list[dict[str, Any]],
        count: int | None = None,
    ):
        self.data = data
        self.count = count


class FakeQueryBuilder:
    """Mimics supabase.table(...).select(...).eq(...).order(...).execute()."""

    def __init__(self, table_name: str, db: dict[str, list[dict[str, Any]]]):
        self._table = table_name
        self._db = db
        self._filters: list[tuple[str, str, Any]] = []
        self._order_col: str | None = None
        self._order_desc: bool = False
        self._limit_val: int | None = None
        self._range_start: int | None = None
        self._range_end: int | None = None
        self._selected_cols: list[str] | None = None
        self._count_mode: str | None = None
        self._in_col: str | None = None
        self._in_values: list[Any] | None = None

    def select(self, *cols, count: str | None = None) -> "FakeQueryBuilder":
        q = copy.copy(self)
        q._selected_cols = list(cols) if cols else None
        q._count_mode = count
        return q

    def eq(self, col: str, value: Any) -> "FakeQueryBuilder":
        q = copy.copy(self)
        q._filters = q._filters + [("eq", col, value)]
        return q

    def neq(self, col: str, value: Any) -> "FakeQueryBuilder":
        q = copy.copy(self)
        q._filters = q._filters + [("neq", col, value)]
        return q

    def gt(self, col: str, value: Any) -> "FakeQueryBuilder":
        q = copy.copy(self)
        q._filters = q._filters + [("gt", col, value)]
        return q

    def lt(self, col: str, value: Any) -> "FakeQueryBuilder":
        q = copy.copy(self)
        q._filters = q._filters + [("lt", col, value)]
        return q

    def gte(self, col: str, value: Any) -> "FakeQueryBuilder":
        q = copy.copy(self)
        q._filters = q._filters + [("gte", col, value)]
        return q

    def lte(self, col: str, value: Any) -> "FakeQueryBuilder":
        q = copy.copy(self)
        q._filters = q._filters + [("lte", col, value)]
        return q

    def in_(self, col: str, values: list[Any]) -> "FakeQueryBuilder":
        """Note: method is 'in_' because 'in' is a Python keyword."""
        q = copy.copy(self)
        q._in_col = col
        q._in_values = values
        return q

    def order(self, col: str, desc: bool = False) -> "FakeQueryBuilder":
        q = copy.copy(self)
        q._order_col = col
        q._order_desc = desc
        return q

    def limit(self, n: int) -> "FakeQueryBuilder":
        q = copy.copy(self)
        q._limit_val = n
        return q

    def range(self, start: int, end: int) -> "FakeQueryBuilder":
        q = copy.copy(self)
        q._range_start = start
        q._range_end = end
        return q

    def _apply_filters(self, rows: list[dict]) -> list[dict]:
        result = list(rows)
        for op, col, value in self._filters:
            if op == "eq":
                result = [r for r in result if r.get(col) == value]
            elif op == "neq":
                result = [r for r in result if r.get(col) != value]
            elif op == "gt":
                result = [r for r in result if r.get(col) is not None and r[col] > value]
            elif op == "lt":
                result = [r for r in result if r.get(col) is not None and r[col] < value]
            elif op == "gte":
                result = [r for r in result if r.get(col) is not None and r[col] >= value]
            elif op == "lte":
                result = [r for r in result if r.get(col) is not None and r[col] <= value]
        if self._in_col and self._in_values:
            result = [r for r in result if r.get(self._in_col) in self._in_values]
        return result

    def _apply_selection(self, rows: list[dict]) -> list[dict]:
        if not self._selected_cols or self._selected_cols == ["*"]:
            return rows
        selected = set(self._selected_cols)
        # Always include id for reference
        result = []
        for r in rows:
            result.append({k: v for k, v in r.items() if k in selected or k == "id"})
        return result

    def execute(self) -> FakeQueryResponse:
        rows = list(self._db.get(self._table, []))

        # Apply filters
        rows = self._apply_filters(rows)

        # Apply ordering
        if self._order_col:
            def _sort_key(r: dict) -> Any:
                val = r.get(self._order_col)
                # Handle None values
                if val is None:
                    return (1, "")  # Nones sort last
                return (0, val)
            rows.sort(key=_sort_key, reverse=self._order_desc)

        # Count
        count_val: int | None = len(rows) if self._count_mode else None

        # Apply range (pagination) before limit
        if self._range_start is not None and self._range_end is not None:
            rows = rows[self._range_start:self._range_end + 1]

        # Apply limit
        if self._limit_val is not None and len(rows) > self._limit_val:
            rows = rows[:self._limit_val]

        # Apply column selection
        rows = self._apply_selection(rows)

        return FakeQueryResponse(data=rows, count=count_val)


class FakeTableBuilder:
    """Mimics supabase.table(name) — returns FakeQueryBuilder for queries."""

    def __init__(self, table_name: str, db: dict[str, list[dict[str, Any]]]):
        self._table = table_name
        self._db = db

    def select(self, *cols, count: str | None = None) -> FakeQueryBuilder:
        return FakeQueryBuilder(self._table, self._db).select(*cols, count=count)

    def insert(self, data: dict | list[dict]) -> FakeQueryBuilder:
        """Insert a row into the in-memory DB."""
        if isinstance(data, dict):
            rows = [data]
        else:
            rows = data

        for row in rows:
            record = dict(row)
            if "id" not in record:
                record["id"] = str(uuid4())
            record.setdefault("created_at", datetime.now().isoformat())
            self._db.setdefault(self._table, []).append(record)

        return FakeQueryBuilder(self._table, self._db).execute()

    def update(self, data: dict) -> "FakeTableBuilder":
        self._pending_update = data
        return self

    def delete(self) -> "FakeTableBuilder":
        self._pending_delete = True
        return self

    def eq(self, col: str, value: Any) -> "FakeTableBuilder":
        self._pending_filter_col = col
        self._pending_filter_val = value
        return self

    def in_(self, col: str, values: list[Any]) -> "FakeTableBuilder":
        self._pending_in_col = col
        self._pending_in_values = values
        return self

    def execute(self) -> FakeQueryResponse:
        table = self._db.get(self._table, [])

        # Handle DELETE
        if getattr(self, "_pending_delete", False):
            col = getattr(self, "_pending_filter_col", None)
            val = getattr(self, "_pending_filter_val", None)
            in_col = getattr(self, "_pending_in_col", None)
            in_vals = getattr(self, "_pending_in_values", None)

            before = len(table)
            if col and val is not None:
                self._db[self._table] = [r for r in table if r.get(col) != val]
            elif in_col and in_vals:
                self._db[self._table] = [r for r in table if r.get(in_col) not in in_vals]
            else:
                self._db[self._table] = []
            deleted_count = before - len(self._db[self._table])

            # Clean up pending attrs
            for attr in ("_pending_delete", "_pending_filter_col", "_pending_filter_val",
                         "_pending_in_col", "_pending_in_values"):
                try:
                    delattr(self, attr)
                except AttributeError:
                    pass

            return FakeQueryResponse(data=[{"deleted": True, "count": deleted_count}])

        # Handle UPDATE
        data = getattr(self, "_pending_update", None)
        if data:
            col = getattr(self, "_pending_filter_col", None)
            val = getattr(self, "_pending_filter_val", None)

            updated = []
            for r in table:
                if col and val is not None and r.get(col) == val:
                    r = {**r, **data}
                    updated.append(r)
                elif col is None:
                    r = {**r, **data}
                    updated.append(r)
                else:
                    updated.append(r)
            self._db[self._table] = updated

            # Clean up
            for attr in ("_pending_update", "_pending_filter_col", "_pending_filter_val",
                         "_pending_in_col", "_pending_in_values"):
                try:
                    delattr(self, attr)
                except AttributeError:
                    pass

            result = [r for r in updated if col is None or r.get(col) == (val if not data else {**r, **data}.get(col))]
            return FakeQueryResponse(data=result[:1])  # Return first match

        # Default: return all for the table
        return FakeQueryResponse(data=list(table))

    def rpc(self, name: str, params: dict | None = None) -> FakeRPCBuilder:
        return FakeRPCBuilder(name, params, self._db)


class FakeRPCBuilder:
    """Mimics supabase.rpc() calls."""

    def __init__(self, name: str, params: dict | None, db: dict):
        self._name = name
        self._params = params or {}
        self._db = db

    def execute(self) -> FakeQueryResponse:
        if self._name == "match_brand_memory":
            return FakeQueryResponse(data=[])
        if self._name == "check_recent_brand_coverage":
            return FakeQueryResponse(data=[])
        if self._name == "match_knowledge_base":
            return FakeQueryResponse(data=[])
        return FakeQueryResponse(data=[])


class FakeSupabaseClient:
    """
    Fake Supabase client for unit tests.
    Usage:
        db = {"drafts": [...], "ideas": [...]}
        client = FakeSupabaseClient(db)
        client.table("drafts").select("*").execute()
    """

    def __init__(self, db: dict[str, list[dict[str, Any]]] | None = None):
        self._db: dict[str, list[dict[str, Any]]] = db or {}
        self._rpc_registry: dict[str, Callable] = {}

    def table(self, name: str) -> FakeTableBuilder:
        return FakeTableBuilder(name, self._db)

    def rpc(self, name: str, params: dict | None = None) -> FakeRPCBuilder:
        return FakeRPCBuilder(name, params, self._db)

    def register_rpc(self, name: str, handler: Callable) -> None:
        self._rpc_registry[name] = handler


def make_test_db() -> dict[str, list[dict[str, Any]]]:
    """Create a fresh in-memory test database with realistic seed data."""
    now = datetime.now()
    from datetime import timedelta

    db: dict[str, list[dict[str, Any]]] = {
        "drafts": [],
        "ideas": [],
        "raw_content": [],
        "curated_sites": [],
        "run_logs": [],
        "cost_log": [],
        "published_posts": [],
        "brand_memory": [],
        "knowledge_base": [],
        "content_analytics": [],
        "user_decision_summaries": [],
        "email_subscribers": [],
    }

    # Seed 15 ideas (oldest first, to test ordering — newest should come first)
    for i in range(15):
        db["ideas"].append({
            "id": str(uuid4()),
            "platform": ["linkedin", "twitter", "blog", "email"][i % 4],
            "angle": f"Test idea {i+1}",
            "edited_angle": None,
            "source_article_id": None,
            "agent_reasoning": f"Reasoning for idea {i+1}",
            "source_article_date": None,
            "approval_status": ["pending_approval", "approved", "rejected"][i % 3],
            "score": round(10.0 - i * 0.5, 1),
            "recent_coverage_flag": False,
            "created_at": (now - timedelta(hours=i)).isoformat(),
            "updated_at": (now - timedelta(hours=i)).isoformat(),
        })

    # Seed 15 drafts
    for i in range(15):
        db["drafts"].append({
            "id": str(uuid4()),
            "platform": ["linkedin", "twitter", "blog", "email"][i % 4],
            "content_text": f"Test draft content {i+1}. " * 20,
            "agent_reasoning": f"Reasoning for draft {i+1}",
            "source_idea_id": None,
            "finance_flags": [],
            "suggested_publish_time": None,
            "scheduled_at": None,
            "approval_status": ["pending_approval", "approved", "rejected"][i % 3],
            "created_at": (now - timedelta(hours=i)).isoformat(),
            "updated_at": (now - timedelta(hours=i)).isoformat(),
        })

    return db