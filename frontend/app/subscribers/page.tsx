"use client";

import { useState, useEffect, useRef } from "react";
import {
  getSubscribers,
  addSubscriber,
  updateSubscriber,
  deleteSubscriber,
  type Subscriber,
} from "../lib/api";

export default function SubscribersPage() {
  const [subscribers, setSubscribers] = useState<Subscriber[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  // Add form state
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

  const [busyIds, setBusyIds] = useState<Set<string>>(new Set());

  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showToast = (msg: string) => {
    if (toastTimerRef.current !== null) clearTimeout(toastTimerRef.current);
    setToast(msg);
    toastTimerRef.current = setTimeout(() => setToast(null), 3000);
  };

  useEffect(() => {
    return () => {
      if (toastTimerRef.current !== null) clearTimeout(toastTimerRef.current);
    };
  }, []);

  const fetchSubscribers = async () => {
    setLoading(true);
    setError(null);
    try {
      setSubscribers(await getSubscribers());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSubscribers();
  }, []);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;
    setAdding(true);
    setAddError(null);
    try {
      const sub = await addSubscriber({ email: email.trim(), name: name.trim() || undefined });
      setSubscribers((prev) => [sub, ...prev]);
      setEmail("");
      setName("");
      showToast("Subscriber added.");
    } catch (e: unknown) {
      setAddError(e instanceof Error ? e.message : "Failed to add");
    } finally {
      setAdding(false);
    }
  };

  const handleToggle = async (sub: Subscriber) => {
    if (busyIds.has(sub.id)) return;
    setBusyIds((prev) => new Set(prev).add(sub.id));
    try {
      const updated = await updateSubscriber(sub.id, { active: !sub.active });
      setSubscribers((prev) => prev.map((s) => (s.id === sub.id ? updated : s)));
      showToast(`${sub.email} ${updated.active ? "activated" : "deactivated"}.`);
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : "Failed to update");
    } finally {
      setBusyIds((prev) => { const n = new Set(prev); n.delete(sub.id); return n; });
    }
  };

  const handleDelete = async (sub: Subscriber) => {
    if (!confirm(`Remove ${sub.email}?`)) return;
    if (busyIds.has(sub.id)) return;
    setBusyIds((prev) => new Set(prev).add(sub.id));
    try {
      await deleteSubscriber(sub.id);
      setSubscribers((prev) => prev.filter((s) => s.id !== sub.id));
      showToast(`${sub.email} removed.`);
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : "Failed to delete");
    } finally {
      setBusyIds((prev) => { const n = new Set(prev); n.delete(sub.id); return n; });
    }
  };

  const unsubscribeLink = (token: string | null) => {
    if (!token || typeof window === "undefined") return null;
    return `${window.location.origin}/unsubscribe?token=${token}`;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Email Subscribers</h1>
          <p className="text-sm text-gray-500 mt-1">
            {loading ? "Loading..." : `${subscribers.length} subscriber${subscribers.length !== 1 ? "s" : ""}`}
          </p>
        </div>
        <button
          onClick={fetchSubscribers}
          disabled={loading}
          className="px-3 py-1.5 text-sm border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        >
          Refresh
        </button>
      </div>

      {toast && (
        <div className="px-4 py-3 rounded-md text-sm bg-green-50 text-green-700 border border-green-200">
          {toast}
        </div>
      )}

      {/* Add subscriber form */}
      <div className="bg-white border border-gray-200 rounded-lg p-4">
        <h2 className="text-sm font-semibold text-gray-700 mb-3">Add Subscriber</h2>
        <form onSubmit={handleAdd} className="flex gap-3 flex-wrap items-end">
          <div className="flex-1 min-w-48">
            <label className="block text-xs text-gray-600 mb-1">Email *</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="someone@example.com"
            />
          </div>
          <div className="flex-1 min-w-36">
            <label className="block text-xs text-gray-600 mb-1">Name (optional)</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Rahul"
            />
          </div>
          <button
            type="submit"
            disabled={adding}
            className="px-4 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
          >
            {adding ? "Adding..." : "Add"}
          </button>
        </form>
        {addError && <p className="text-xs text-red-600 mt-2">{addError}</p>}
      </div>

      {/* Subscribers table */}
      {error && (
        <div className="px-4 py-3 rounded-md text-sm bg-red-50 text-red-700 border border-red-200">
          {error}
        </div>
      )}

      {!loading && !error && subscribers.length === 0 && (
        <div className="text-center py-12 text-gray-500 text-sm">No subscribers yet.</div>
      )}

      {subscribers.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500">Email</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500">Name</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500">Status</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500">Subscribed</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500">Unsubscribe Link</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {subscribers.map((sub) => {
                const link = unsubscribeLink(sub.unsubscribe_token);
                return (
                  <tr key={sub.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-gray-900 font-medium">{sub.email}</td>
                    <td className="px-4 py-3 text-gray-600">{sub.name ?? "—"}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                          sub.active
                            ? "bg-green-100 text-green-700"
                            : "bg-gray-100 text-gray-500"
                        }`}
                      >
                        {sub.active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">
                      {sub.subscribed_date
                        ? new Date(sub.subscribed_date).toLocaleDateString()
                        : "—"}
                    </td>
                    <td className="px-4 py-3 text-xs">
                      {link ? (
                        <button
                          onClick={async () => {
                            try {
                              await navigator.clipboard.writeText(link);
                              showToast("Link copied!");
                            } catch {
                              showToast("Failed to copy link");
                            }
                          }}
                          className="text-blue-600 hover:underline"
                        >
                          Copy link
                        </button>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleToggle(sub)}
                          disabled={busyIds.has(sub.id)}
                          className="text-xs text-blue-600 hover:underline disabled:opacity-50"
                        >
                          {sub.active ? "Deactivate" : "Activate"}
                        </button>
                        <button
                          onClick={() => handleDelete(sub)}
                          disabled={busyIds.has(sub.id)}
                          className="text-xs text-red-600 hover:underline disabled:opacity-50"
                        >
                          Remove
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
