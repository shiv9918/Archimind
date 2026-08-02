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

const NODE_WIDTH = 200;
const NODE_HEIGHT = 44;

const TYPE_COLOR: Record<string, string> = {
  File: "#0ea5e9",
  Class: "#a855f7",
  Function: "#22c55e",
  Module: "#f59e0b",
};

const EDGE_COLOR: Record<string, string> = {
  defines: "#475569",
  imports: "#f59e0b",
  inherits: "#a855f7",
  calls: "#22c55e",
};

function layout(nodes: GraphNode[], edges: GraphEdge[]) {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: "LR", nodesep: 30, ranksep: 90 });
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

export default function KnowledgeGraphView({
  nodes,
  edges,
  onNodeClick,
}: {
  nodes: GraphNode[];
  edges: GraphEdge[];
  onNodeClick: (nodeId: string) => void;
}) {
  const { flowNodes, flowEdges } = useMemo(() => {
    const positioned = layout(nodes, edges);

    const flowNodes: Node[] = positioned.map((n) => ({
      id: n.id,
      position: { x: n.x, y: n.y },
      data: { label: n.label },
      style: {
        width: NODE_WIDTH,
        border: `1.5px solid ${TYPE_COLOR[n.type] ?? "#64748b"}`,
        background: "#0f172a",
        color: "#e2e8f0",
        borderRadius: 8,
        fontSize: 12,
        padding: 8,
      },
    }));

    const flowEdges: Edge[] = edges
      .filter((e) => positioned.some((n) => n.id === e.source) && positioned.some((n) => n.id === e.target))
      .map((e, i) => ({
        id: `${e.source}-${e.target}-${e.type}-${i}`,
        source: e.source,
        target: e.target,
        label: e.type,
        style: { stroke: EDGE_COLOR[e.type] ?? "#64748b" },
        markerEnd: { type: MarkerType.ArrowClosed, color: EDGE_COLOR[e.type] ?? "#64748b" },
        labelStyle: { fill: "#94a3b8", fontSize: 10 },
      }));

    return { flowNodes, flowEdges };
  }, [nodes, edges]);

  return (
    <div className="h-[70vh] w-full overflow-hidden rounded-xl border border-slate-800 bg-slate-950">
      <ReactFlow
        nodes={flowNodes}
        edges={flowEdges}
        onNodeClick={(_, node) => onNodeClick(node.id)}
        fitView
        colorMode="dark"
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
