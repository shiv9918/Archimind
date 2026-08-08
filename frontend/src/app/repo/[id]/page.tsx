"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, ApiError, type DashboardResponse } from "@/lib/api";
import HealthScoreCard from "@/components/HealthScoreCard";
import RepoOverviewPanel from "@/components/RepoOverviewPanel";
import ArchitecturePanel from "@/components/ArchitecturePanel";
import RecommendationsList from "@/components/RecommendationsList";

export default function RepoDashboardPage() {
  const { id } = useParams<{ id: string }>();
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .getDashboard(id)
      .then((res) => {
        setDashboard(res);
        setError(null);
      })
      .catch((err) => {
        if (err instanceof ApiError) {
          setError(err.message);
        } else {
          // A generic fetch failure (network error/CORS block) almost always means the
          // backend hasn't responded at all yet -- most commonly Render's free tier
          // spinning the service back up from sleep. Polling keeps retrying, so this
          // clears itself once the backend answers.
          setError("Can't reach the ArchMind backend right now -- it may be waking up from sleep. Retrying automatically...");
        }
      });
  }, [id]);

  useEffect(() => {
    load();
    const interval = setInterval(load, 3000);
    return () => clearInterval(interval);
  }, [load]);

  if (error) return <p className="text-sm text-red-400">{error}</p>;
  if (!dashboard) return <p className="text-sm text-slate-500">Loading dashboard...</p>;

  if (!dashboard.ready) {
    const failed = dashboard.latest_job_status === "failed";
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-8 text-center">
        {failed ? (
          <>
            <p className="text-red-400 font-medium">Scan failed</p>
            <p className="mt-2 text-sm text-slate-500">{dashboard.latest_job_error}</p>
            <button
              onClick={() => api.rescan(id).then(load)}
              className="mt-4 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500"
            >
              Retry scan
            </button>
          </>
        ) : (
          <>
            <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-slate-700 border-t-indigo-500" />
            <p className="mt-4 text-sm text-slate-400">
              {dashboard.latest_job_stage ? `Stage: ${dashboard.latest_job_stage}` : "Preparing scan..."}
            </p>
            <p className="mt-1 text-xs text-slate-600">This page updates automatically.</p>
          </>
        )}
      </div>
    );
  }

  const { overview, architecture, health, recommendations } = dashboard;

  return (
    <div className="space-y-8">
      <section>
        <h2 className="mb-3 text-sm font-semibold text-slate-300">Repository Health</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {health && (
            <>
              <HealthScoreCard label="Architecture Score" value={health.architecture_score} notes={health.notes.architecture} />
              <HealthScoreCard label="Security Score" value={health.security_score_basic} notes={health.notes.security} />
              <HealthScoreCard label="Performance Score" value={null} unavailable />
              <HealthScoreCard label="Documentation Score" value={health.documentation_score} notes={health.notes.documentation} />
              <HealthScoreCard label="Technical Debt" value={health.technical_debt_index} invert notes={health.notes.technical_debt} />
              <HealthScoreCard label="Test Coverage (est.)" value={health.test_coverage_estimated} notes={health.notes.test_coverage} />
              <HealthScoreCard label="Code Complexity" value={health.complexity_score} notes={health.notes.complexity} />
              <HealthScoreCard label="Dependency Health" value={health.dependency_health_score} notes={health.notes.dependency_health} />
            </>
          )}
        </div>
      </section>

      {overview && <RepoOverviewPanel overview={overview} />}

      <div className="grid gap-6 lg:grid-cols-2">
        {architecture && <ArchitecturePanel architecture={architecture} />}
        {recommendations && <RecommendationsList recommendations={recommendations} />}
      </div>
    </div>
  );
}
