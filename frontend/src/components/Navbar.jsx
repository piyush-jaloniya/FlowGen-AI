import React from "react";

export default function Navbar() {
    return (
        <div className="header">
            <div style={{ fontWeight: 700, fontSize: 20 }}>CodeVis AI</div>
            <div className="nav">
                <div className="small">Home</div>
                <div className="small">Flowchart</div>
                <div className="small">Workflow</div>
                <div className="small">About</div>
            </div>
        </div>
    );
}
