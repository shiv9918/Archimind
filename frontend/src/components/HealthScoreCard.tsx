function colorFor(value: number, invert: boolean) {
  const effective = invert ? 100 - value : value;
  if (effective >= 75) return { bar: "bg-emerald-500", text: "text-emerald-300" };
  if (effective >= 50) return { bar: "bg-amber-500", text: "text-amber-300" };
  return { bar: "bg-red-500", text: "text-red-300" };
}

export default function HealthScoreCard({
  label,
  value,
  invert = false,
  notes,
  unavailable = false,
}: {
  label: string;
  value: number | null;
  invert?: boolean;
  notes?: string[];
  unavailable?: boolean;
}) {
  if (unavailable || value === null) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
        <div className="text-sm text-slate-400">{label}</div>
        <div className="mt-2 text-lg font-semibold text-slate-500">Coming soon</div>
        <p className="mt-1 text-xs text-slate-500">Requires runtime profiling -- planned for a later phase.</p>
      </div>
    );
  }

  const { bar, text } = colorFor(value, invert);

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
      <div className="text-sm text-slate-400">{label}</div>
      <div className={`mt-1 text-2xl font-bold ${text}`}>{value}{typeof value === "number" ? (invert ? "" : "%") : ""}</div>
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
        <div className={`h-full rounded-full ${bar}`} style={{ width: `${Math.min(100, Math.max(0, value))}%` }} />
      </div>
      {notes && notes.length > 0 && (
        <ul className="mt-2 space-y-0.5 text-xs text-slate-500">
          {notes.slice(0, 2).map((n, i) => (
            <li key={i} className="truncate" title={n}>{n}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
