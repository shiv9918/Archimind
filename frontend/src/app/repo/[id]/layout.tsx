"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useParams } from "next/navigation";
import { api, type Repository } from "@/lib/api";
import StatusBadge from "@/components/StatusBadge";

const TABS = [
  { href: "", label: "Dashboard" },
  { href: "/graph", label: "Knowledge Graph" },
  { href: "/chat", label: "Developer Copilot" },
];

export default function RepoLayout({ children }: { children: React.ReactNode }) {
  const params = useParams<{ id: string }>();
  const pathname = usePathname();
  const repoId = params.id;
  const [repo, setRepo] = useState<Repository | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.getRepo(repoId).then((r) => {
      if (!cancelled) setRepo(r);
    }).catch(() => {});
    const interval = setInterval(() => {
      api.getRepo(repoId).then((r) => {
        if (!cancelled) setRepo(r);
      }).catch(() => {});
    }, 4000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [repoId]);

  const base = `/repo/${repoId}`;

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

      <div className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">{children}</div>
    </div>
  );
}
