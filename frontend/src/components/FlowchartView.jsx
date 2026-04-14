import React, { useState } from "react";
import ReactFlow, { Background, Controls } from "reactflow";
import "reactflow/dist/style.css";
import axios from "axios";

const Flowchart = () => {
    const [nodes, setNodes] = useState([]);
    const [edges, setEdges] = useState([]);
    const [code, setCode] = useState("");

    const generateFlowchart = async () => {
        try {
            const API_URL = process.env.REACT_APP_API_URL || "http://127.0.0.1:8000/api";
            const response = await axios.post(`${API_URL}/analyze`, {
                filename: "test.js",
                content: code,
            });

            console.log("Backend response:", response.data);

            // Fix: support both old and new API formats
            const flowchartData = response.data.flowchart || response.data;
            const backendNodes = flowchartData.nodes || [];
            const backendEdges = flowchartData.edges || [];

            if (backendNodes.length === 0) {
                alert("No nodes received from backend!");
            }

            // Convert backend node format to React Flow
            const mappedNodes = backendNodes.map((n, i) => ({
                id: n.id || `node-${i}`,
                data: { label: n.label || n.name || "Node" },
                position: { x: 150 * i, y: 100 },
            }));

            const mappedEdges = backendEdges.map((e, i) => ({
                id: e.id || `edge-${i}`,
                source: e.from || e.source || backendNodes[0]?.id,
                target: e.to || e.target || backendNodes[1]?.id,
                animated: true,
            }));

            setNodes(mappedNodes);
            setEdges(mappedEdges);
        } catch (error) {
            console.error("Error fetching flowchart:", error);
            alert("Error generating flowchart — see console for details.");
        }
    };

    return (
        <div style={{ width: "100%", height: "100vh", display: "flex", flexDirection: "column" }}>
            <textarea
                placeholder="Enter code here..."
                value={code}
                onChange={(e) => setCode(e.target.value)}
                style={{ width: "100%", height: "200px", fontFamily: "monospace", marginBottom: "10px" }}
            />
            <button
                onClick={generateFlowchart}
                style={{ padding: "8px 16px", backgroundColor: "#007bff", color: "white", border: "none", borderRadius: "5px" }}
            >
                Generate Flowchart
            </button>
            <div style={{ flex: 1, marginTop: "10px" }}>
                <ReactFlow nodes={nodes} edges={edges} fitView>
                    <Background />
                    <Controls />
                </ReactFlow>
            </div>
        </div>
    );
};

export default Flowchart;
