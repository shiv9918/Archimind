"use client";

import { useEffect, useState } from "react";
import { api, type Repository } from "@/lib/api";
import ImportPanel from "@/components/ImportPanel";
import RepoCard from "@/components/RepoCard";

export default function HomePage() {
  const [repos, setRepos] = useState<Repository[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listRepos()
      .then(setRepos)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load repositories"));
  }, []);

  return (
    <main className="mx-auto w-full max-w-5xl flex-1 px-6 py-10">
      <header className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight text-slate-100">ArchMind AI</h1>
        <p className="mt-1 text-sm text-slate-400">
          Autonomous codebase architect -- import a repository to build its knowledge graph, health scores, and AI copilot.
        </p>
      </header>

      <ImportPanel />

      <section className="mt-10">
        <h2 className="text-sm font-semibold text-slate-300">Imported repositories</h2>

        {error && <p className="mt-3 text-sm text-red-400">{error}</p>}

        {repos === null && !error && <p className="mt-3 text-sm text-slate-500">Loading...</p>}

        {repos !== null && repos.length === 0 && (
          <p className="mt-3 text-sm text-slate-500">No repositories imported yet. Add one above to get started.</p>
        )}

        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {repos?.map((repo) => <RepoCard key={repo.id} repo={repo} />)}
        </div>
      </section>
    </main>
  );
}
