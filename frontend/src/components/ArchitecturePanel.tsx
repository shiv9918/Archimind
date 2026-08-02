import type { ArchitectureReport } from "@/lib/api";

export default function ArchitecturePanel({ architecture }: { architecture: ArchitectureReport }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
      <h2 className="text-sm font-semibold text-slate-300">System Architecture</h2>

      <div className="mt-3 flex items-baseline gap-3">
        <span className="text-xl font-bold text-indigo-300">{architecture.primary_pattern}</span>
        <span className="text-sm text-slate-500">{Math.round(architecture.primary_confidence * 100)}% confidence</span>
      </div>
      <p className="mt-2 text-sm text-slate-400">{architecture.summary}</p>

      {architecture.is_microservices && (
        <p className="mt-2 text-xs text-slate-500">{architecture.service_count} independently deployable service(s) detected.</p>
      )}

      {architecture.matches.length > 1 && (
        <div className="mt-4">
          <h3 className="text-xs uppercase tracking-wide text-slate-500">Other signals detected</h3>
          <ul className="mt-2 space-y-1.5">
            {architecture.matches.slice(1, 5).map((m) => (
              <li key={m.pattern} className="flex items-center justify-between text-xs text-slate-400">
                <span>{m.pattern}</span>
                <span className="text-slate-600">{Math.round(m.confidence * 100)}%</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
