const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export type Repository = {
  id: string;
  name: string;
  source_type: string;
  source_ref: string;
  status: string;
  created_at: string;
};

export type ScanJob = {
  id: string;
  repository_id: string;
  status: "pending" | "running" | "done" | "failed";
  stage: string;
  error_message: string | null;
  result: Record<string, unknown> | null;
  created_at: string;
  finished_at: string | null;
};

export type HealthScores = {
  architecture_score: number;
  documentation_score: number;
  complexity_score: number;
  test_coverage_estimated: number;
  dependency_health_score: number;
  security_score_basic: number;
  technical_debt_index: number;
  performance_score: null;
  notes: Record<string, string[]>;
  security_findings: { file: string; line: number; rule: string }[];
};

export type RepositoryOverview = {
  total_files: number;
  total_dirs: number;
  languages: Record<string, number>;
  frameworks: string[];
  package_managers: string[];
  databases: string[];
  third_party_apis: string[];
  has_docker: boolean;
  has_kubernetes: boolean;
  ci_cd: string[];
  has_readme: boolean;
  env_files: string[];
  migration_dirs: string[];
  dependency_count: number;
};

export type ArchitectureReport = {
  primary_pattern: string;
  primary_confidence: number;
  matches: { pattern: string; confidence: number; matched_signals: string[] }[];
  is_microservices: boolean;
  service_count: number;
  summary: string;
};

export type GraphStats = {
  total_nodes: number;
  total_edges: number;
  nodes_by_type: Record<string, number>;
  edges_by_type: Record<string, number>;
  most_depended_on: { id: string; in_degree: number }[];
  most_coupled: { id: string; out_degree: number }[];
};

export type DashboardResponse = {
  repository: { id: string; name: string; status: string };
  ready: boolean;
  scan_job_id?: string;
  scanned_at?: string;
  overview?: RepositoryOverview;
  graph_stats?: GraphStats;
  architecture?: ArchitectureReport;
  health?: HealthScores;
  recommendations?: string[];
  parse_errors?: { file: string; error: string }[];
  files_parsed?: number;
  latest_job_status?: string | null;
  latest_job_stage?: string | null;
  latest_job_error?: string | null;
  message?: string;
};

export type GraphNode = { id: string; type: string; label: string; properties: Record<string, unknown> };
export type GraphEdge = { source: string; target: string; type: string };
export type GraphResponse = { nodes: GraphNode[]; edges: GraphEdge[]; truncated: boolean; view: "package" | "file" | null };

export type ChatMessageOut = { id: string; role: "user" | "assistant"; content: string; created_at: string };

class ApiError extends Error {}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      // ignore -- fall back to statusText
    }
    throw new ApiError(detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  listRepos: () => request<Repository[]>("/api/repos"),
  getRepo: (id: string) => request<Repository>(`/api/repos/${id}`),
  deleteRepo: (id: string) => request<{ status: string }>(`/api/repos/${id}`, { method: "DELETE" }),

  importGithub: (url: string) =>
    request<{ repository: Repository; scan_job_id: string }>("/api/repos/import/github", {
      method: "POST",
      body: JSON.stringify({ url }),
    }),

  importZip: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${API_BASE}/api/repos/import/zip`, { method: "POST", body: form });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new ApiError(body.detail || res.statusText);
    }
    return res.json() as Promise<{ repository: Repository; scan_job_id: string }>;
  },

  rescan: (id: string) => request<{ scan_job_id: string }>(`/api/repos/${id}/rescan`, { method: "POST" }),
  latestScan: (id: string) => request<ScanJob>(`/api/repos/${id}/scan/latest`),
  getDashboard: (id: string) => request<DashboardResponse>(`/api/repos/${id}/dashboard`),

  getGraph: (id: string, nodeId?: string, depth = 1) => {
    const params = new URLSearchParams();
    if (nodeId) params.set("node_id", nodeId);
    params.set("depth", String(depth));
    return request<GraphResponse>(`/api/repos/${id}/graph?${params.toString()}`);
  },

  getChatHistory: (id: string) => request<ChatMessageOut[]>(`/api/repos/${id}/chat`),
  postChat: (id: string, message: string) =>
    request<{ message: ChatMessageOut; sources: { id: string; type: string; file: string; score: number }[] }>(
      `/api/repos/${id}/chat`,
      { method: "POST", body: JSON.stringify({ message }) }
    ),
};

export { ApiError };
