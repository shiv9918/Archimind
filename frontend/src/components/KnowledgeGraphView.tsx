"use client";

import { useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import dagre from "dagre";
import type { GraphNode, GraphEdge } from "@/lib/api";

const NODE_WIDTH = 190;
const NODE_HEIGHT = 40;

const TYPE_COLOR: Record<string, string> = {
  Package: "#ec4899",
  File: "#0ea5e9",
  Class: "#a855f7",
  Function: "#22c55e",
  Module: "#f59e0b",
};

const EDGE_COLOR: Record<string, string> = {
  contains: "#334155",
  defines: "#475569",
  imports: "#f59e0b",
  inherits: "#a855f7",
  calls: "#22c55e",
};

const NODE_TYPE_ORDER = ["Package", "File", "Class", "Function", "Module"];
const EDGE_TYPE_ORDER = ["contains", "defines", "inherits", "calls", "imports"];

function basename(path: string): string {
  const parts = path.split("/");
  return parts[parts.length - 1] || path;
}

function displayLabel(node: GraphNode): string {
  if (node.type === "File") return basename(node.label);
  if (node.type === "Package") {
    const count = node.properties.file_count;
    return typeof count === "number" ? `${node.label} (${count})` : node.label;
  }
  return node.label;
}

function tooltipFor(node: GraphNode): string | undefined {
  if (node.type === "File") return node.label;
  if (node.type === "Package") return typeof node.properties.path === "string" ? node.properties.path : undefined;
  return undefined;
}

function layout(nodes: GraphNode[], edges: GraphEdge[]) {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: "LR", nodesep: 45, ranksep: 140, marginx: 20, marginy: 20 });
  g.setDefaultEdgeLabel(() => ({}));

  nodes.forEach((n) => g.setNode(n.id, { width: NODE_WIDTH, height: NODE_HEIGHT }));
  edges.forEach((e) => {
    if (g.hasNode(e.source) && g.hasNode(e.target)) g.setEdge(e.source, e.target);
  });

  dagre.layout(g);

  return nodes.map((n) => {
    const pos = g.node(n.id);
    return { ...n, x: pos?.x ?? 0, y: pos?.y ?? 0 };
  });
}

function Legend({ nodeTypes, edgeTypes }: { nodeTypes: string[]; edgeTypes: string[] }) {
  if (nodeTypes.length === 0 && edgeTypes.length === 0) return null;
  return (
    <div className="pointer-events-none absolute left-3 top-3 z-10 rounded-lg border border-slate-800 bg-slate-950/90 px-3 py-2 text-xs text-slate-400 backdrop-blur">
      {nodeTypes.length > 0 && (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          {nodeTypes.map((t) => (
            <span key={t} className="flex items-center gap-1.5">
              <span
                className="inline-block h-2.5 w-2.5 rounded-sm"
                style={{ border: `1.5px solid ${TYPE_COLOR[t] ?? "#64748b"}` }}
              />
              {t}
            </span>
          ))}
        </div>
      )}
      {edgeTypes.length > 0 && (
        <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1">
          {edgeTypes.map((t) => (
            <span key={t} className="flex items-center gap-1.5">
              <span className="inline-block h-0.5 w-3" style={{ background: EDGE_COLOR[t] ?? "#64748b" }} />
              {t}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export default function KnowledgeGraphView({
  nodes,
  edges,
  onNodeClick,
}: {
  nodes: GraphNode[];
  edges: GraphEdge[];
  onNodeClick: (nodeId: string) => void;
}) {
  const { flowNodes, flowEdges, nodeTypes, edgeTypes } = useMemo(() => {
    const positioned = layout(nodes, edges);

    const flowNodes: Node[] = positioned.map((n) => ({
      id: n.id,
      position: { x: n.x, y: n.y },
      // Explicit width/height (not just CSS) let React Flow compute edge
      // anchor points immediately instead of waiting on a DOM measurement pass.
      width: NODE_WIDTH,
      height: NODE_HEIGHT,
      data: {
        label: <span title={tooltipFor(n)}>{displayLabel(n)}</span>,
      },
      style: {
        width: NODE_WIDTH,
        height: NODE_HEIGHT,
        border: `${n.type === "Package" ? 2 : 1.5}px solid ${TYPE_COLOR[n.type] ?? "#64748b"}`,
        background: n.type === "Package" ? "#1e1b2e" : "#0f172a",
        color: "#e2e8f0",
        fontWeight: n.type === "Package" ? 600 : 400,
        borderRadius: 8,
        fontSize: 12,
        padding: 8,
        overflow: "hidden",
        textOverflow: "ellipsis",
        whiteSpace: "nowrap",
      },
    }));

    const flowEdges: Edge[] = edges
      .filter((e) => positioned.some((n) => n.id === e.source) && positioned.some((n) => n.id === e.target))
      .map((e, i) => ({
        // A plain index-based id -- edge ids get embedded in generated SVG
        // marker URLs (url(#...)), and real node ids here can contain spaces
        // and parentheses (from file paths), which breaks that reference.
        id: `edge-${i}`,
        source: e.source,
        target: e.target,
        style: { stroke: EDGE_COLOR[e.type] ?? "#64748b", strokeWidth: 1.25, opacity: 0.7 },
        markerEnd: { type: MarkerType.ArrowClosed, color: EDGE_COLOR[e.type] ?? "#64748b" },
      }));

    const presentNodeTypes = NODE_TYPE_ORDER.filter((t) => nodes.some((n) => n.type === t));
    const presentEdgeTypes = EDGE_TYPE_ORDER.filter((t) => edges.some((e) => e.type === t));

    return { flowNodes, flowEdges, nodeTypes: presentNodeTypes, edgeTypes: presentEdgeTypes };
  }, [nodes, edges]);

  return (
    <div className="relative h-[70vh] w-full overflow-hidden rounded-xl border border-slate-800 bg-slate-950">
      <Legend nodeTypes={nodeTypes} edgeTypes={edgeTypes} />
      <ReactFlow
        nodes={flowNodes}
        edges={flowEdges}
        onNodeClick={(_, node) => onNodeClick(node.id)}
        fitView
        colorMode="dark"
        minZoom={0.1}
      >
        <Background color="#1e293b" gap={20} />
        <Controls />
        <MiniMap
          nodeColor={(n) => {
            const original = nodes.find((gn) => gn.id === n.id);
            return original ? (TYPE_COLOR[original.type] ?? "#64748b") : "#64748b";
          }}
          maskColor="rgba(2, 6, 23, 0.7)"
        />
      </ReactFlow>
    </div>
  );
}
