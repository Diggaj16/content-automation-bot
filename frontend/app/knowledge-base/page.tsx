"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { uploadKbFile, listKbFiles, deleteKbFile, type KbFile } from "../lib/api";

export default function KnowledgeBasePage() {
  const [files, setFiles] = useState<KbFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [busyFiles, setBusyFiles] = useState<Set<string>>(new Set());
  const fileInputRef = useRef<HTMLInputElement>(null);
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showToast = useCallback((msg: string) => {
    if (toastTimerRef.current !== null) clearTimeout(toastTimerRef.current);
    setToast(msg);
    toastTimerRef.current = setTimeout(() => setToast(null), 4000);
  }, []);

  useEffect(() => {
    return () => {
      if (toastTimerRef.current !== null) clearTimeout(toastTimerRef.current);
    };
  }, []);

  const fetchFiles = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setFiles(await listKbFiles());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchFiles();
  }, [fetchFiles]);

  const handleUpload = async (file: File) => {
    if (!file.name.match(/\.(pdf|txt)$/i)) {
      showToast("Only PDF and TXT files are supported.");
      return;
    }
    setUploading(true);
    try {
      const result = await uploadKbFile(file);
      showToast(`Uploaded "${result.source_file}" — ${result.chunks_ingested} chunks ingested.`);
      await fetchFiles();
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleUpload(file);
    e.target.value = "";
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleUpload(file);
  };

  const handleDelete = async (sourceFile: string) => {
    if (!confirm(`Delete all chunks for "${sourceFile}"?`)) return;
    if (busyFiles.has(sourceFile)) return;
    setBusyFiles((prev) => new Set(prev).add(sourceFile));
    try {
      await deleteKbFile(sourceFile);
      setFiles((prev) => prev.filter((f) => f.source_file !== sourceFile));
      showToast(`Deleted "${sourceFile}".`);
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : "Delete failed");
    } finally {
      setBusyFiles((prev) => { const n = new Set(prev); n.delete(sourceFile); return n; });
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Knowledge Base</h1>
          <p className="text-sm text-gray-500 mt-1">
            Upload PDF or TXT files to use as context in KB-driven and combined content.
          </p>
        </div>
        <button
          onClick={fetchFiles}
          disabled={loading}
          className="px-3 py-1.5 text-sm border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        >
          Refresh
        </button>
      </div>

      {toast && (
        <div className="px-4 py-3 rounded-md text-sm bg-blue-50 text-blue-700 border border-blue-200">
          {toast}
        </div>
      )}

      {/* Upload zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`border-2 border-dashed rounded-lg p-10 text-center cursor-pointer transition-colors ${
          dragOver
            ? "border-blue-400 bg-blue-50"
            : "border-gray-300 hover:border-gray-400 bg-white"
        } ${uploading ? "opacity-60 pointer-events-none" : ""}`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.txt"
          className="hidden"
          onChange={handleFileInput}
        />
        <div className="text-3xl mb-2">📄</div>
        <p className="text-sm font-medium text-gray-700">
          {uploading ? "Uploading..." : "Drop a PDF or TXT file here, or click to browse"}
        </p>
        <p className="text-xs text-gray-400 mt-1">Max size determined by server config</p>
      </div>

      {/* File list */}
      {error && (
        <div className="px-4 py-3 rounded-md text-sm bg-red-50 text-red-700 border border-red-200">
          {error}
        </div>
      )}

      {!loading && !error && files.length === 0 && (
        <div className="text-center py-12 text-gray-500 text-sm">
          No files ingested yet. Upload a PDF or TXT to get started.
        </div>
      )}

      {files.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500">File</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500">Chunks</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500">Uploaded</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {files.map((f) => (
                <tr key={f.source_file} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-gray-900 font-medium">{f.source_file}</td>
                  <td className="px-4 py-3 text-gray-600">{f.chunk_count}</td>
                  <td className="px-4 py-3 text-gray-500 text-xs">
                    {new Date(f.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => handleDelete(f.source_file)}
                      disabled={busyFiles.has(f.source_file)}
                      className="text-xs text-red-600 hover:underline disabled:opacity-50"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
