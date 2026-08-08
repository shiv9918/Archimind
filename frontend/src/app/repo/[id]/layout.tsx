"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useParams, useRouter } from "next/navigation";
import { api, ApiError, type Repository } from "@/lib/api";
import StatusBadge from "@/components/StatusBadge";
import { getRepoSource, moveRepoSource } from "@/lib/repoSource";

const TABS = [
  { href: "", label: "Dashboard" },
  { href: "/graph", label: "Knowledge Graph" },
  { href: "/chat", label: "Developer Copilot" },
];

// Keyed by repoId in the parent so a change of repo (including the swap to a
// freshly re-imported id, see `recover()` below) remounts this component --
// a clean slate for `repo`/`recovery` state instead of an effect that resets
// it, which would call setState synchronously during the effect and trigger
// a needless extra render.
function RepoPoller({
  repoId,
  base,
  pathname,
  router,
  children,
}: {
  repoId: string;
  base: string;
  pathname: string;
  router: ReturnType<typeof useRouter>;
  children: React.ReactNode;
}) {
  const [repo, setRepo] = useState<Repository | null>(null);
  const [recovery, setRecovery] = useState<"idle" | "recovering" | "failed">("idle");
  const recoveringRef = useRef(false);
  const pathnameRef = useRef(pathname);

  useEffect(() => {
    pathnameRef.current = pathname;
  }, [pathname]);

  useEffect(() => {
    let cancelled = false;

    async function recover() {
      if (recoveringRef.current || cancelled) return;
      recoveringRef.current = true;
      const source = getRepoSource(repoId);
      if (!source) {
        if (!cancelled) setRecovery("failed");
        return;
      }
      setRecovery("recovering");
      try {
        const { repository } = await api.importGithub(source.url);
        moveRepoSource(repoId, repository.id);
        if (!cancelled) router.replace(`/repo/${repository.id}${pathnameRef.current.slice(base.length)}`);
      } catch {
        if (!cancelled) setRecovery("failed");
      }
    }

    function poll() {
      api
        .getRepo(repoId)
        .then((r) => {
          if (!cancelled) setRepo(r);
        })
        .catch((err) => {
          // The backend's disk is ephemeral (resets on restart/redeploy), so a
          // repo that's genuinely gone shows up as a 404 rather than a
          // transient network error -- try to transparently re-import it.
          if (err instanceof ApiError && err.message === "Repository not found") {
            recover();
          }
        });
    }

    poll();
    const interval = setInterval(poll, 4000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [repoId, base, router]);

  return (
    <div className="flex flex-1 flex-col">
      <div className="border-b border-slate-800 bg-slate-950/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3 min-w-0">
            <Link href="/" className="shrink-0 text-sm text-slate-500 hover:text-slate-300">ArchMind AI /</Link>
            <span className="truncate font-medium text-slate-100">{repo?.name ?? repoId}</span>
            {repo && <StatusBadge status={repo.status} />}
          </div>
        </div>
        <div className="mx-auto flex max-w-6xl gap-1 px-6">
          {TABS.map((tab) => {
            const href = `${base}${tab.href}`;
            const active = pathname === href;
            return (
              <Link
                key={tab.href}
                href={href}
                className={`border-b-2 px-3 py-2 text-sm transition ${
                  active
                    ? "border-indigo-500 text-slate-100"
                    : "border-transparent text-slate-500 hover:text-slate-300"
                }`}
              >
                {tab.label}
              </Link>
            );
          })}
        </div>
      </div>

      <div className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">
        {recovery === "recovering" ? (
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-8 text-center">
            <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-slate-700 border-t-indigo-500" />
            <p className="mt-4 text-sm text-slate-400">
              The backend&apos;s free-tier storage reset (it restarted), so this repository was lost. Re-importing it
              automatically...
            </p>
          </div>
        ) : recovery === "failed" ? (
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-8 text-center">
            <p className="font-medium text-red-400">This repository is no longer available</p>
            <p className="mt-2 text-sm text-slate-500">
              The backend&apos;s free-tier storage resets on restart, and there&apos;s no saved source to
              automatically re-import it (this happens for ZIP uploads, or a new browser/device).
            </p>
            <Link
              href="/"
              className="mt-4 inline-block rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500"
            >
              Import again
            </Link>
          </div>
        ) : (
          children
        )}
      </div>
    </div>
  );
}

export default function RepoLayout({ children }: { children: React.ReactNode }) {
  const params = useParams<{ id: string }>();
  const pathname = usePathname();
  const router = useRouter();
  const repoId = params.id;
  const base = `/repo/${repoId}`;

  return (
    <RepoPoller key={repoId} repoId={repoId} base={base} pathname={pathname} router={router}>
      {children}
    </RepoPoller>
  );
}
