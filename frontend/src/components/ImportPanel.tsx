"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { saveRepoSource } from "@/lib/repoSource";

export default function ImportPanel() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function handleGithubImport(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const { repository } = await api.importGithub(url.trim());
      saveRepoSource(repository.id, url.trim());
      router.push(`/repo/${repository.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Import failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleZipImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setBusy(true);
    try {
      const { repository } = await api.importZip(file);
      router.push(`/repo/${repository.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Import failed");
    } finally {
      setBusy(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
      <h2 className="text-sm font-semibold text-slate-300">Import a repository</h2>

      <form onSubmit={handleGithubImport} className="mt-3 flex gap-2">
        <input
          type="text"
          required
          placeholder="https://github.com/owner/repo"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          disabled={busy}
          className="flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-indigo-500 focus:outline-none"
        />
        <button
          type="submit"
          disabled={busy}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
        >
          {busy ? "Importing..." : "Connect GitHub"}
        </button>
      </form>

      <div className="mt-3 flex items-center gap-3 text-xs text-slate-600">
        <div className="h-px flex-1 bg-slate-800" />
        or
        <div className="h-px flex-1 bg-slate-800" />
      </div>

      <label className="mt-3 flex cursor-pointer items-center justify-center rounded-lg border border-dashed border-slate-700 px-4 py-3 text-sm text-slate-400 hover:border-indigo-600/60 hover:text-slate-200">
        <input ref={fileInputRef} type="file" accept=".zip" onChange={handleZipImport} disabled={busy} className="hidden" />
        {busy ? "Uploading..." : "Upload a .zip archive"}
      </label>

      {error && <p className="mt-3 text-sm text-red-400">{error}</p>}
    </div>
  );
}
