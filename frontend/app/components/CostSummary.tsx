"use client";

import { useEffect, useState } from "react";
import { getTableRows } from "../lib/api";

type Totals = {
  total: number;
  month: number;
  today: number;
  tokens: number;
  rowCount: number;
};

const usd = (n: number) =>
  "$" + n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function Stat({
  label,
  value,
  primary = false,
}: {
  label: string;
  value: string;
  primary?: boolean;
}) {
  return (
    <div className="flex flex-col">
      <span className="text-[11px] uppercase tracking-wide text-gray-400">{label}</span>
      <span
        className="tabular-nums font-semibold leading-tight"
        style={
          primary
            ? { fontSize: "1.5rem", color: "var(--brand-text)" }
            : { fontSize: "1.05rem", color: "var(--text-primary)" }
        }
      >
        {value}
      </span>
    </div>
  );
}

/** All-time spend summary for the cost_log table. Pages through every row
 *  (batches of 500) so the total is exact, not just the visible page. */
export default function CostSummary() {
  const [totals, setTotals] = useState<Totals | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const BATCH = 500;
        const rows: Record<string, unknown>[] = [];
        let offset = 0;
        let count = Infinity;
        while (offset < count) {
          const resp = await getTableRows("cost_log", {
            limit: BATCH,
            offset,
            orderBy: "date",
            orderDesc: true,
          });
          rows.push(...resp.rows);
          count = resp.count ?? rows.length;
          if (resp.rows.length < BATCH) break;
          offset += BATCH;
        }
        if (cancelled) return;

        const todayStr = new Date().toISOString().slice(0, 10);
        const monthStr = todayStr.slice(0, 7);
        let total = 0, month = 0, today = 0, tokens = 0;
        for (const r of rows) {
          const c = Number(r.estimated_cost_usd) || 0;
          const date = String(r.date ?? "");
          total += c;
          if (date.slice(0, 7) === monthStr) month += c;
          if (date.slice(0, 10) === todayStr) today += c;
          tokens += Number(r.token_count) || 0;
        }
        setTotals({ total, month, today, tokens, rowCount: rows.length });
      } catch (e: unknown) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load cost summary");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-800">
        Couldn&rsquo;t compute cost total: {error}
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white px-5 py-4 flex flex-wrap items-center gap-x-10 gap-y-3">
      {loading || !totals ? (
        <span className="text-sm text-gray-400">Calculating total spend…</span>
      ) : (
        <>
          <Stat label="Total spend" value={usd(totals.total)} primary />
          <Stat label="This month" value={usd(totals.month)} />
          <Stat label="Today" value={usd(totals.today)} />
          <Stat label="Tokens used" value={totals.tokens.toLocaleString()} />
          <span className="text-xs text-gray-400 ml-auto self-end">
            across {totals.rowCount} log entr{totals.rowCount !== 1 ? "ies" : "y"}
          </span>
        </>
      )}
    </div>
  );
}
