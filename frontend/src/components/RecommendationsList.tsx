export default function RecommendationsList({ recommendations }: { recommendations: string[] }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
      <h2 className="text-sm font-semibold text-slate-300">Recommended Improvements</h2>
      <ul className="mt-3 space-y-2">
        {recommendations.map((rec, i) => (
          <li key={i} className="flex gap-2 text-sm text-slate-300">
            <span className="mt-0.5 text-indigo-400">-</span>
            <span>{rec}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
