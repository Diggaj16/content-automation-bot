"use client";

import { useState, useEffect, useCallback } from "react";
import {
  getTableRows,
  deleteTableRow,
  type TableListResponse,
} from "../lib/api";

const PAGE_SIZE = 25;

function CellValue({ value }: { value: string | number | boolean | object | null | undefined }) {
  if (value === null || value === undefined) {
    return <span className="text-gray-300 italic">null</span>;
  }
  if (typeof value === "boolean") {
    return (
      <span
        className={`inline-block px-1.5 py-0.5 rounded text-xs font-medium ${
          value ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"
        }`}
      >
        {value ? "true" : "false"}
      </span>
    );
  }
  if (typeof value === "object") {
    const json = JSON.stringify(value);
    if (json.length > 120) {
      return (
        <details className="inline">
          <summary className="cursor-pointer text-xs text-blue-600 hover:underline">
            {json.slice(0, 80)}…
          </summary>
          <pre className="mt-1 text-xs bg-gray-50 p-2 rounded max-h-48 overflow-auto whitespace-pre-wrap">
            {JSON.stringify(value, null, 2)}
          </pre>
        </details>
      );
    }
    return <span className="text-xs font-mono">{json}</span>;
  }
  const str = String(value);
  // Truncate very long strings (e.g. full_text scraped content)
  if (str.length > 300) {
    return (
      <details className="inline">
        <summary className="cursor-pointer text-xs text-blue-600 hover:underline">
          {str.slice(0, 120)}…
        </summary>
        <p className="mt-1 text-xs bg-gray-50 p-2 rounded max-h-48 overflow-auto whitespace-pre-wrap">
          {str}
        </p>
      </details>
    );
  }
  return <span>{str}</span>;
}

export default function TableBrowser({
  tableName,
  title,
}: {
  tableName: string;
  title?: string;
}) {
  const [data, setData] = useState<TableListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  // orderBy is initialised from data.default_sort on first load
  const [orderBy, setOrderBy] = useState("created_at");
  const [orderDesc, setOrderDesc] = useState(true);
  const [filterCol, setFilterCol] = useState("");
  const [filterVal, setFilterVal] = useState("");
  const [activeFilter, setActiveFilter] = useState<{ col: string; val: string } | null>(null);

  // When the first page of data arrives, adopt the backend's recommended sort column
  // (e.g. style_guide → updated_at). Only update if still on the generic default.
  useEffect(() => {
    if (data?.default_sort && orderBy === "created_at" && !data.columns.includes("created_at")) {
      setOrderBy(data.default_sort);
    }
  }, [data, orderBy]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getTableRows(tableName, {
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
        orderBy,
        orderDesc,
        filterColumn: activeFilter?.col || undefined,
        filterValue: activeFilter?.val,
      });
      setData(result);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [tableName, page, orderBy, orderDesc, activeFilter]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleSort = (col: string) => {
    if (orderBy === col) {
      setOrderDesc(!orderDesc);
    } else {
      setOrderBy(col);
      setOrderDesc(true);
    }
    setPage(0);
  };

  const handleFilter = () => {
    if (filterCol && filterVal) {
      setActiveFilter({ col: filterCol, val: filterVal });
    } else {
      setActiveFilter(null);
    }
    setPage(0);
  };

  const clearFilter = () => {
    setFilterCol("");
    setFilterVal("");
    setActiveFilter(null);
    setPage(0);
  };

  const handleDelete = async (rowId: string) => {
    if (!confirm("Delete this row?")) return;
    try {
      await deleteTableRow(tableName, rowId);
      fetchData();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Delete failed");
    }
  };

  // Columns from the loaded data (backend strips vector columns)
  const columns = data?.columns ?? (data && data.rows.length > 0 ? Object.keys(data.rows[0]) : []);
  const totalCount = data?.count ?? 0;
  const totalPages = Math.ceil(totalCount / PAGE_SIZE);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">{title || tableName}</h1>
          <p className="text-xs text-gray-500 mt-0.5">
            {loading ? "Loading…" : `${totalCount} row${totalCount !== 1 ? "s" : ""}`}
          </p>
        </div>
        <button
          onClick={fetchData}
          disabled={loading}
          className="px-3 py-1.5 text-sm border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        >
          Refresh
        </button>
      </div>

      {/* Filter bar — column is a <select> to prevent arbitrary column injection */}
      <div className="flex items-center gap-2 flex-wrap">
        <select
          value={filterCol}
          onChange={(e) => setFilterCol(e.target.value)}
          className="border border-gray-300 rounded px-2 py-1 text-sm w-40 bg-white disabled:opacity-50"
          disabled={columns.length === 0}
        >
          <option value="">— column —</option>
          {columns.map((col) => (
            <option key={col} value={col}>
              {col}
            </option>
          ))}
        </select>
        <input
          type="text"
          placeholder="Value"
          value={filterVal}
          onChange={(e) => setFilterVal(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleFilter()}
          className="border border-gray-300 rounded px-2 py-1 text-sm w-48"
        />
        <button
          onClick={handleFilter}
          disabled={!filterCol || !filterVal}
          className="px-3 py-1 text-sm bg-gray-100 border border-gray-300 rounded hover:bg-gray-200 disabled:opacity-40"
        >
          Filter
        </button>
        {activeFilter && (
          <button
            onClick={clearFilter}
            className="px-3 py-1 text-sm text-red-600 border border-red-200 rounded hover:bg-red-50"
          >
            Clear filter
          </button>
        )}
        {activeFilter && (
          <span className="text-xs text-gray-500">
            {activeFilter.col} = &ldquo;{activeFilter.val}&rdquo;
          </span>
        )}
      </div>

      {error && (
        <div className="px-4 py-3 rounded-md text-sm bg-red-50 text-red-700 border border-red-200">
          {error}
        </div>
      )}

      {data && data.rows.length === 0 && !loading && (
        <div className="text-center py-8 text-gray-400 text-sm">No rows found.</div>
      )}

      {data && data.rows.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-gray-200">
          <table className="min-w-full text-xs">
            <thead className="bg-gray-50 text-gray-600 uppercase tracking-wide">
              <tr>
                {columns.map((col) => (
                  <th
                    key={col}
                    className="px-3 py-2 text-left cursor-pointer hover:bg-gray-100 whitespace-nowrap select-none"
                    onClick={() => handleSort(col)}
                  >
                    {col}
                    {orderBy === col && (
                      <span className="ml-1">{orderDesc ? "▼" : "▲"}</span>
                    )}
                  </th>
                ))}
                <th className="px-3 py-2 text-left">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {data.rows.map((row, i) => (
                <tr key={(row.id as string) || i} className="hover:bg-gray-50">
                  {columns.map((col) => (
                    <td key={col} className="px-3 py-2 text-gray-700 max-w-xs">
                      <CellValue value={row[col] as never} />
                    </td>
                  ))}
                  <td className="px-3 py-2">
                    {typeof row.id === "string" && (
                      <button
                        onClick={() => handleDelete(row.id as string)}
                        className="text-red-500 hover:text-red-700 text-xs"
                      >
                        Delete
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm">
          <button
            onClick={() => setPage(Math.max(0, page - 1))}
            disabled={page === 0}
            className="px-3 py-1 border border-gray-300 rounded disabled:opacity-40 hover:bg-gray-50"
          >
            Previous
          </button>
          <span className="text-gray-500">
            Page {page + 1} of {totalPages}
          </span>
          <button
            onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
            disabled={page >= totalPages - 1}
            className="px-3 py-1 border border-gray-300 rounded disabled:opacity-40 hover:bg-gray-50"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
