import Link from "next/link";
import type { Repository } from "@/lib/api";
import StatusBadge from "./StatusBadge";

export default function RepoCard({ repo }: { repo: Repository }) {
  return (
    <Link
      href={`/repo/${repo.id}`}
      className="block rounded-xl border border-slate-800 bg-slate-900/60 p-4 transition hover:border-indigo-600/60 hover:bg-slate-900"
    >
      <div className="flex items-center justify-between">
        <span className="truncate font-medium text-slate-100">{repo.name}</span>
        <StatusBadge status={repo.status} />
      </div>
      <div className="mt-1 truncate text-xs text-slate-500">{repo.source_ref}</div>
      <div className="mt-2 text-xs text-slate-600">
        {repo.source_type === "github" ? "GitHub import" : "ZIP upload"} - {new Date(repo.created_at).toLocaleString()}
      </div>
    </Link>
  );
}
