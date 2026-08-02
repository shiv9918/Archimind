import type { RepositoryOverview } from "@/lib/api";

function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-md border border-slate-700 bg-slate-800/60 px-2 py-1 text-xs text-slate-300">
      {children}
    </span>
  );
}

export default function RepoOverviewPanel({ overview }: { overview: RepositoryOverview }) {
  const languageEntries = Object.entries(overview.languages).sort((a, b) => b[1] - a[1]);
  const totalLangFiles = languageEntries.reduce((sum, [, count]) => sum + count, 0) || 1;

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
      <h2 className="text-sm font-semibold text-slate-300">Repository Overview</h2>

      <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Files" value={overview.total_files} />
        <Stat label="Directories" value={overview.total_dirs} />
        <Stat label="Dependencies" value={overview.dependency_count} />
        <Stat label="Env files" value={overview.env_files.length} />
      </div>

      <div className="mt-5">
        <h3 className="text-xs uppercase tracking-wide text-slate-500">Languages</h3>
        <div className="mt-2 space-y-1.5">
          {languageEntries.slice(0, 8).map(([lang, count]) => (
            <div key={lang} className="flex items-center gap-2 text-xs">
              <span className="w-24 shrink-0 truncate text-slate-400">{lang}</span>
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-800">
                <div
                  className="h-full rounded-full bg-indigo-500"
                  style={{ width: `${(count / totalLangFiles) * 100}%` }}
                />
              </div>
              <span className="w-10 shrink-0 text-right text-slate-500">{count}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <Group title="Frameworks" items={overview.frameworks} empty="None detected" />
        <Group title="Package managers" items={overview.package_managers} empty="None detected" />
        <Group title="Databases" items={overview.databases} empty="None detected" />
        <Group title="Third-party APIs" items={overview.third_party_apis} empty="None detected" />
      </div>

      <div className="mt-5 flex flex-wrap gap-2">
        <Chip>{overview.has_docker ? "Docker: yes" : "Docker: no"}</Chip>
        <Chip>{overview.has_kubernetes ? "Kubernetes: yes" : "Kubernetes: no"}</Chip>
        <Chip>{overview.has_readme ? "README: present" : "README: missing"}</Chip>
        {overview.ci_cd.map((c) => (
          <Chip key={c}>CI/CD: {c}</Chip>
        ))}
        {overview.migration_dirs.length > 0 && <Chip>{overview.migration_dirs.length} migration dir(s)</Chip>}
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg bg-slate-800/40 px-3 py-2">
      <div className="text-lg font-semibold text-slate-100">{value}</div>
      <div className="text-xs text-slate-500">{label}</div>
    </div>
  );
}

function Group({ title, items, empty }: { title: string; items: string[]; empty: string }) {
  return (
    <div>
      <h3 className="text-xs uppercase tracking-wide text-slate-500">{title}</h3>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {items.length === 0 ? (
          <span className="text-xs text-slate-600">{empty}</span>
        ) : (
          items.map((item) => <Chip key={item}>{item}</Chip>)
        )}
      </div>
    </div>
  );
}
