import React, { useState } from "react";

export default function CodeEditor({ onCodeChange, onFileChange }) {
    const [code, setCode] = useState("");

    function handlePasteChange(e) {
        const val = e.target.value;
        setCode(val);
        onCodeChange(val);
    }

    function handleFile(ev) {
        const f = ev.target.files[0];
        if (!f) return;
        onFileChange(f);
        const reader = new FileReader();
        reader.onload = (e) => {
            const txt = e.target.result;
            setCode(txt);
            onCodeChange(txt);
        };
        reader.readAsText(f);
    }

    return (
        <div className="panel">
            <h3>Code Input</h3>
            <div style={{ marginBottom: 8 }}>
                <input type="file" accept=".py,.js,.java,.txt" onChange={handleFile} />
            </div>
            <textarea
                placeholder="Paste code here..."
                value={code}
                onChange={handlePasteChange}
                style={{ width: "100%", height: 280, fontFamily: "monospace", fontSize: 13, padding: 8 }}
            />
        </div>
    );
}
