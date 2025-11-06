import React from "react";
import ReactFlow, { Controls, MiniMap, Background } from "reactflow";

function mapWorkflowToElements(workJson) {
    if (!workJson) return [];
    const nodes = (workJson.nodes || []).map((n, idx) => ({
        id: n.id,
        data: { label: n.label, full: n.full_text },
        position: { x: (idx % 4) * 240 + 60, y: Math.floor(idx / 4) * 140 + 60 },
        style: { padding: 10, borderRadius: 6, background: "#fff", border: "1px solid #e6e9ee" },
    }));
    const edges = (workJson.edges || []).map((e, idx) => ({
        id: `w${idx}`,
        source: e.from,
        target: e.to,
        animated: false,
        label: e.type || "",
    }));
    return [...nodes, ...edges];
}

export default function WorkflowView({ workflow }) {
    const elements = mapWorkflowToElements(workflow);

    const onElementClick = (e, el) => {
        if (el?.data?.full) {
            alert(el.data.full);
        }
    };

    return (
        <div className="panel" style={{ height: 600 }}>
            <h3>Workflow</h3>
            {!workflow && <div className="small">Generate a workflow to preview here.</div>}
            {workflow && (
                <ReactFlow elements={elements} onElementClick={onElementClick}>
                    <MiniMap />
                    <Controls />
                    <Background gap={20} />
                </ReactFlow>
            )}
        </div>
    );
}
