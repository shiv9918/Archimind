"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, type GraphNode, type GraphEdge } from "@/lib/api";
import KnowledgeGraphView from "@/components/KnowledgeGraphView";

const TYPE_COLOR: Record<string, string> = {
  Package: "text-pink-400",
  File: "text-sky-400",
  Class: "text-purple-400",
  Function: "text-emerald-400",
  Module: "text-amber-400",
};

export default function RepoGraphPage() {
  const { id } = useParams<{ id: string }>();
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [truncated, setTruncated] = useState(false);
  const [view, setView] = useState<"package" | "file" | null>(null);
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .getGraph(id)
      .then((res) => {
        setNodes(res.nodes);
        setEdges(res.edges);
        setTruncated(res.truncated);
        setView(res.view);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load graph"))
      .finally(() => setLoading(false));
  }, [id]);

  const handleNodeClick = useCallback(
    (nodeId: string) => {
      const node = nodes.find((n) => n.id === nodeId) ?? null;
      setSelected(node);

      api.getGraph(id, nodeId, 1).then((res) => {
        setNodes((prev) => {
          const existingIds = new Set(prev.map((n) => n.id));
          const merged = [...prev];
          for (const n of res.nodes) if (!existingIds.has(n.id)) merged.push(n);
          return merged;
        });
        setEdges((prev) => {
          const key = (e: GraphEdge) => `${e.source}->${e.target}:${e.type}`;
          const existingKeys = new Set(prev.map(key));
          const merged = [...prev];
          for (const e of res.edges) if (!existingKeys.has(key(e))) merged.push(e);
          return merged;
        });
      });
    },
    [id, nodes]
  );

  if (error) return <p className="text-sm text-red-400">{error}</p>;
  if (loading) return <p className="text-sm text-slate-500">Loading knowledge graph...</p>;

  if (nodes.length === 0) {
    return <p className="text-sm text-slate-500">No graph data yet -- the repository may still be scanning.</p>;
  }

  return (
    <div className="space-y-3">
      <p className="rounded-lg border border-slate-800 bg-slate-900/60 px-3 py-2 text-xs text-slate-400">
        {view === "package"
          ? "Showing the system architecture -- each node is a module/folder, arrows show which module depends on which. Click a module to reveal its files, then click a file for its classes and functions."
          : "Showing files and classes for a clean overview. Click any node to expand its functions, imports, and calls."}
        {truncated && " This repository is large, so some lower-connectivity nodes are hidden from the initial view."}
      </p>

      <div className="flex gap-4">
        <div className="flex-1">
          <KnowledgeGraphView nodes={nodes} edges={edges} onNodeClick={handleNodeClick} />
        </div>

        <aside className="w-72 shrink-0 rounded-xl border border-slate-800 bg-slate-900/60 p-4">
          <h3 className="text-sm font-semibold text-slate-300">Node details</h3>
          {selected ? (
            <div className="mt-3 space-y-2 text-xs">
              <div className={`text-sm font-medium ${TYPE_COLOR[selected.type] ?? "text-slate-300"}`}>{selected.type}</div>
              <div className="break-words text-slate-100">{selected.label}</div>
              {Object.entries(selected.properties)
                .filter(([k]) => k !== "docstring")
                .map(([k, v]) => (
                  <div key={k} className="text-slate-500">
                    <span className="text-slate-600">{k}:</span> {String(v)}
                  </div>
                ))}
              {typeof selected.properties.docstring === "string" && selected.properties.docstring && (
                <p className="mt-2 rounded-md bg-slate-800/50 p-2 text-slate-400">{selected.properties.docstring}</p>
              )}
            </div>
          ) : (
            <p className="mt-3 text-xs text-slate-500">Click a node to see its details and expand its relationships.</p>
          )}
        </aside>
      </div>
    </div>
  );
}
