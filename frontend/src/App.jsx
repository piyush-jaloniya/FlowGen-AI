import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import Editor from "@monaco-editor/react";
import mermaid from "mermaid";
import { toPng } from 'html-to-image';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import "./App.css";

const API_URL = process.env.REACT_APP_API_URL || "http://127.0.0.1:8000/api";

function App() {
    const [code, setCode] = useState("");
    const [flowchartMermaid, setFlowchartMermaid] = useState("");
    const [workflowMermaid, setWorkflowMermaid] = useState("");
    const [loading, setLoading] = useState(false);
    const [inputMode, setInputMode] = useState("snippet"); // snippet, file, folder
    const [selectedFiles, setSelectedFiles] = useState([]);
    const [processedInfo, setProcessedInfo] = useState(null);
    const [activeTab, setActiveTab] = useState("flowchart"); // flowchart, workflow, ai-insights
    const [editorLanguage, setEditorLanguage] = useState("python"); // editor language
    const [isFullscreen, setIsFullscreen] = useState(false); // fullscreen state
    const [showExportMenu, setShowExportMenu] = useState(false); // export menu dropdown
    const [aiInsights, setAiInsights] = useState(null); // AI-powered insights
    const flowchartRef = useRef(null);
    const workflowRef = useRef(null);
    const fullscreenFlowchartRef = useRef(null);
    const fullscreenWorkflowRef = useRef(null);

    useEffect(() => {
        document.title = "FlowGen AI: The Unified Code Visualization Engine for Flowcharts and Workflows";

        // Initialize Mermaid
        mermaid.initialize({
            startOnLoad: false,
            theme: 'dark',
            securityLevel: 'loose',
            flowchart: {
                useMaxWidth: true,
                htmlLabels: true,
                curve: 'basis'
            }
        });
    }, []);

    // Re-render Mermaid diagrams when content changes
    useEffect(() => {
        const renderDiagrams = async () => {
            if (flowchartMermaid && flowchartRef.current && activeTab === "flowchart") {
                try {
                    console.log("Rendering flowchart diagram...");
                    flowchartRef.current.innerHTML = flowchartMermaid;
                    flowchartRef.current.removeAttribute('data-processed');
                    await mermaid.run({ nodes: [flowchartRef.current] });
                } catch (error) {
                    console.error("Error rendering flowchart:", error);
                }
            }
        };
        renderDiagrams();
    }, [flowchartMermaid, activeTab]);

    useEffect(() => {
        const renderDiagrams = async () => {
            if (workflowMermaid && workflowRef.current && activeTab === "workflow") {
                try {
                    console.log("Rendering workflow diagram...");
                    workflowRef.current.innerHTML = workflowMermaid;
                    workflowRef.current.removeAttribute('data-processed');
                    await mermaid.run({ nodes: [workflowRef.current] });
                } catch (error) {
                    console.error("Error rendering workflow:", error);
                }
            }
        };
        renderDiagrams();
    }, [workflowMermaid, activeTab]);

    // Render fullscreen diagrams
    useEffect(() => {
        const renderFullscreen = async () => {
            if (isFullscreen && flowchartMermaid && fullscreenFlowchartRef.current && activeTab === "flowchart") {
                try {
                    console.log("Rendering fullscreen flowchart...");
                    fullscreenFlowchartRef.current.innerHTML = flowchartMermaid;
                    fullscreenFlowchartRef.current.removeAttribute('data-processed');
                    await mermaid.run({ nodes: [fullscreenFlowchartRef.current] });
                } catch (error) {
                    console.error("Error rendering fullscreen flowchart:", error);
                }
            }
            if (isFullscreen && workflowMermaid && fullscreenWorkflowRef.current && activeTab === "workflow") {
                try {
                    console.log("Rendering fullscreen workflow...");
                    fullscreenWorkflowRef.current.innerHTML = workflowMermaid;
                    fullscreenWorkflowRef.current.removeAttribute('data-processed');
                    await mermaid.run({ nodes: [fullscreenWorkflowRef.current] });
                } catch (error) {
                    console.error("Error rendering fullscreen workflow:", error);
                }
            }
        };
        renderFullscreen();
    }, [isFullscreen, flowchartMermaid, workflowMermaid, activeTab]);

    // Close export menu when clicking outside
    useEffect(() => {
        const handleClickOutside = (event) => {
            if (showExportMenu && !event.target.closest('.export-dropdown')) {
                setShowExportMenu(false);
            }
        };

        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [showExportMenu]);

    const generateData = async (type = "both") => {
        // Check input based on mode
        if (inputMode === "snippet" && !code.trim()) {
            alert("Please enter some code first!");
            return;
        }
        if ((inputMode === "file" || inputMode === "folder") && selectedFiles.length === 0) {
            alert("Please select files to upload!");
            return;
        }

        setLoading(true);
        try {
            let response;

            // Handle snippet mode (existing functionality)
            if (inputMode === "snippet") {
                let endpoint = "/analyze";
                if (type === "flowchart") endpoint = "/flowchart";
                else if (type === "workflow") endpoint = "/workflow";

                // Generate proper filename based on selected language
                const languageExtensions = {
                    python: "input.py",
                    javascript: "input.js",
                    java: "input.java",
                    c: "input.c",
                    cpp: "input.cpp"
                };
                const filename = languageExtensions[editorLanguage] || "input.txt";

                response = await axios.post(`${API_URL}${endpoint}`, {
                    filename: filename,
                    content: code,
                });
            }
            // Handle file/folder upload mode
            else {
                const formData = new FormData();

                // Both folder and file modes append files the same way
                for (let i = 0; i < selectedFiles.length; i++) {
                    formData.append("files", selectedFiles[i]);
                }

                response = await axios.post(`${API_URL}/analyze-multiple`, formData, {
                    headers: {
                        "Content-Type": "multipart/form-data",
                    },
                    maxBodyLength: Infinity,
                    maxContentLength: Infinity,
                });
            }

            console.log("Backend response:", response.data);

            // Safely extract data
            const data = response.data || {};
            const flowchart = data.flowchart || {};
            const workflow = data.workflow || {};

            // Store processed file info if available
            if (data.processed_files) {
                setProcessedInfo({
                    files: data.processed_files,
                    total: data.total_files
                });
            }

            // Store AI insights if available
            if (data.ai_insights) {
                console.log("AI Insights received:", data.ai_insights);
                setAiInsights(data.ai_insights);
            } else {
                console.log("No AI insights in response");
                setAiInsights(null);
            }

            // Update states with Mermaid code
            if (type === "both" || type === "flowchart") {
                setFlowchartMermaid(flowchart.mermaid || "");
            }
            if (type === "both" || type === "workflow") {
                setWorkflowMermaid(workflow.mermaid || "");
            }
        } catch (error) {
            console.error("Error generating data:", error);
            alert("Error fetching visualization data. Check console for details.");
        } finally {
            setLoading(false);
        }
    };

    const handleFileChange = (e) => {
        const files = Array.from(e.target.files);
        setSelectedFiles(files);
    };

    const exportAsJSON = () => {
        const mermaidCode = activeTab === "flowchart" ? flowchartMermaid : workflowMermaid;

        if (!mermaidCode) {
            alert("No diagram to export. Generate a diagram first!");
            return;
        }

        const data = {
            type: activeTab,
            mermaid: mermaidCode,
            timestamp: new Date().toISOString(),
            language: editorLanguage
        };

        const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `${activeTab}-${Date.now()}.json`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        setShowExportMenu(false);
    };

    const exportAsPNG = async () => {
        const ref = activeTab === "flowchart" ? flowchartRef : workflowRef;

        if (!ref.current) {
            alert("No diagram to export. Generate a diagram first!");
            return;
        }

        try {
            const dataUrl = await toPng(ref.current, {
                backgroundColor: '#0f1729',
                width: ref.current.offsetWidth,
                height: ref.current.offsetHeight,
                style: {
                    width: ref.current.offsetWidth + 'px',
                    height: ref.current.offsetHeight + 'px',
                }
            });

            const link = document.createElement('a');
            link.download = `${activeTab}-${Date.now()}.png`;
            link.href = dataUrl;
            link.click();
            setShowExportMenu(false);
        } catch (err) {
            console.error('Failed to export PNG:', err);
            alert('Failed to export as PNG. Please try again.');
        }
    };

    const exportAsMermaid = () => {
        const mermaidCode = activeTab === "flowchart" ? flowchartMermaid : workflowMermaid;

        if (!mermaidCode) {
            alert("No diagram to export. Generate a diagram first!");
            return;
        }

        const blob = new Blob([mermaidCode], { type: "text/plain" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `${activeTab}-${Date.now()}.mmd`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        setShowExportMenu(false);
    }; const toggleFullscreen = () => {
        setIsFullscreen(!isFullscreen);
    };

    return (
        <div className="app-container">
            <header>
                <h1>FlowGen AI</h1>
                <p>The Unified Code Visualization Engine for Flowcharts and Workflows</p>
            </header>

            <div className="main-layout">
                {/* Left Panel */}
                <div className="input-section">
                    {/* Input Mode Selector */}
                    <div className="mode-selector">
                        <label>Input Mode</label>
                        <select
                            value={inputMode}
                            onChange={(e) => {
                                setInputMode(e.target.value);
                                setProcessedInfo(null);
                                setSelectedFiles([]);
                            }}
                        >
                            <option value="snippet">💻 Code Snippet</option>
                            <option value="file">📄 Upload File(s)</option>
                            <option value="folder">📁 Upload Folder (ZIP)</option>
                        </select>
                    </div>

                    {/* Code Snippet Input */}
                    {inputMode === "snippet" && (
                        <>
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                                <p className="input-label" style={{ margin: 0 }}>Code Input</p>
                                <select
                                    value={editorLanguage}
                                    onChange={(e) => setEditorLanguage(e.target.value)}
                                    style={{
                                        padding: "6px 12px",
                                        fontSize: "14px",
                                        border: "2px solid #374151",
                                        borderRadius: "6px",
                                        background: "#0f1729",
                                        color: "#e5e7eb",
                                        cursor: "pointer"
                                    }}
                                >
                                    <option value="python">Python</option>
                                    <option value="javascript">JavaScript</option>
                                    <option value="java">Java</option>
                                    <option value="c">C</option>
                                    <option value="cpp">C++</option>
                                </select>
                            </div>
                            <div className="editor-container">
                                <Editor
                                    height="450px"
                                    language={editorLanguage}
                                    theme="vs-dark"
                                    value={code}
                                    onChange={(value) => setCode(value || "")}
                                    options={{
                                        minimap: { enabled: false },
                                        fontSize: 16,
                                        automaticLayout: true,
                                    }}
                                />
                            </div>
                        </>
                    )}

                    {/* File Upload Input */}
                    {inputMode === "file" && (
                        <>
                            <p className="input-label">Upload Code File(s)</p>
                            <div className="file-upload-container">
                                <input
                                    type="file"
                                    id="file-upload"
                                    multiple
                                    accept=".py,.js,.java,.c,.cpp,.cc,.h,.hpp"
                                    onChange={handleFileChange}
                                />
                                <label htmlFor="file-upload" className="file-upload-label">
                                    📁 Click to select files or drag and drop
                                    <br />
                                    <small>Supported: .py, .js, .java, .c, .cpp, .h, .hpp</small>
                                </label>
                            </div>
                            {selectedFiles.length > 0 && (
                                <div className="file-list">
                                    <div className="file-list-title">Selected files: {selectedFiles.length}</div>
                                    <ul>
                                        {selectedFiles.map((file, idx) => (
                                            <li key={idx}>{file.name}</li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                        </>
                    )}

                    {/* Folder Upload Input */}
                    {inputMode === "folder" && (
                        <>
                            <p className="input-label">Upload Project Folder (ZIP)</p>
                            <div className="file-upload-container">
                                <input
                                    type="file"
                                    id="folder-upload"
                                    accept=".zip"
                                    onChange={handleFileChange}
                                />
                                <label htmlFor="folder-upload" className="file-upload-label">
                                    📦 Click to select ZIP file
                                    <br />
                                    <small>ZIP your project folder first</small>
                                </label>
                            </div>
                            {selectedFiles.length > 0 && (
                                <div className="file-list">
                                    <div className="file-list-title">
                                        Selected: {selectedFiles[0].name} ({(selectedFiles[0].size / 1024).toFixed(2)} KB)
                                    </div>
                                </div>
                            )}
                        </>
                    )}

                    {/* Processed Files Info */}
                    {processedInfo && (
                        <div className="processed-info">
                            <strong>✅ Processed {processedInfo.total} file(s):</strong>
                            <ul>
                                {processedInfo.files.map((file, idx) => (
                                    <li key={idx}>
                                        {file.filename} ({file.language}) - {file.size} chars
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}

                    <div className="button-group">
                        <button onClick={() => generateData("both")} disabled={loading} className="btn-primary">
                            {loading ? "⚡ Processing..." : "⚡ Generate Diagrams"}
                        </button>
                    </div>
                </div>

                {/* Right Panel - Visualization */}
                <div className="visualization-section">
                    {/* Tab Navigation */}
                    <div className="tab-navigation">
                        <div className="tab-buttons">
                            <button
                                className={`tab-btn ${activeTab === "flowchart" ? "active" : ""}`}
                                onClick={() => setActiveTab("flowchart")}
                            >
                                📊 Flowchart
                            </button>
                            <button
                                className={`tab-btn ${activeTab === "workflow" ? "active" : ""}`}
                                onClick={() => setActiveTab("workflow")}
                            >
                                🔄 Workflow
                            </button>
                            <button
                                className={`tab-btn ${activeTab === "ai-insights" ? "active" : ""}`}
                                onClick={() => setActiveTab("ai-insights")}
                                disabled={!aiInsights}
                            >
                                🤖 AI Insights
                            </button>
                        </div>

                        {/* Action Buttons */}
                        <div className="action-buttons">
                            <div className="export-dropdown">
                                <button
                                    className="action-btn"
                                    onClick={() => setShowExportMenu(!showExportMenu)}
                                    disabled={
                                        (activeTab === "flowchart" && !flowchartMermaid) ||
                                        (activeTab === "workflow" && !workflowMermaid)
                                    }
                                >
                                    💾 Export ▼
                                </button>
                                {showExportMenu && (
                                    <div className="export-menu">
                                        <button onClick={exportAsJSON}>📄 Export as JSON</button>
                                        <button onClick={exportAsPNG}>🖼️ Export as PNG</button>
                                        <button onClick={exportAsMermaid}>🔷 Export as Mermaid</button>
                                    </div>
                                )}
                            </div>
                            <button
                                className="action-btn"
                                onClick={toggleFullscreen}
                                disabled={
                                    (activeTab === "flowchart" && !flowchartMermaid) ||
                                    (activeTab === "workflow" && !workflowMermaid)
                                }
                            >
                                ⛶ Fullscreen
                            </button>
                        </div>
                    </div>

                    {/* Visualization Content */}
                    <div className="visualization-content">
                        {activeTab === "flowchart" && (
                            <div className="flow-container">
                                {flowchartMermaid ? (
                                    <div
                                        ref={flowchartRef}
                                        className="mermaid-diagram"
                                    />
                                ) : (
                                    <div className="empty-state">
                                        <div className="empty-icon">📊</div>
                                        <h3>Visualization Appears Here</h3>
                                        <p>Enter your code, click "Generate Diagrams", and watch the magic happen.</p>
                                    </div>
                                )}
                            </div>
                        )}

                        {activeTab === "workflow" && (
                            <div className="flow-container">
                                {workflowMermaid ? (
                                    <div
                                        ref={workflowRef}
                                        className="mermaid-diagram"
                                    />
                                ) : (
                                    <div className="empty-state">
                                        <div className="empty-icon">🔄</div>
                                        <h3>Visualization Appears Here</h3>
                                        <p>Enter your code, click "Generate Diagrams", and watch the magic happen.</p>
                                    </div>
                                )}
                            </div>
                        )}

                        {activeTab === "ai-insights" && (
                            <div className="flow-container">
                                {aiInsights ? (
                                    <div className="ai-insights-tab">
                                        <h2>🤖 AI-Powered Code Analysis</h2>

                                        {aiInsights.description && (
                                            <div className="insight-card">
                                                <div className="card-header">
                                                    <h3>📝 Code Explanation</h3>
                                                    <button
                                                        className="copy-btn"
                                                        onClick={(e) => {
                                                            navigator.clipboard.writeText(aiInsights.description);
                                                            e.target.textContent = '✓ Copied!';
                                                            setTimeout(() => e.target.textContent = '📋 Copy', 2000);
                                                        }}
                                                    >
                                                        📋 Copy
                                                    </button>
                                                </div>
                                                <div className="markdown-content">
                                                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                                        {aiInsights.description}
                                                    </ReactMarkdown>
                                                </div>
                                            </div>
                                        )}

                                        {aiInsights.pattern && (
                                            <div className="insight-card">
                                                <h3>🎯 Algorithm Pattern Detected</h3>
                                                <div className="pattern-badge-large">{aiInsights.pattern}</div>
                                            </div>
                                        )}

                                        {aiInsights.suggestions && (
                                            <div className="insight-card">
                                                <div className="card-header">
                                                    <h3>💡 Code Improvements</h3>
                                                    <button
                                                        className="copy-btn"
                                                        onClick={(e) => {
                                                            navigator.clipboard.writeText(aiInsights.suggestions);
                                                            e.target.textContent = '✓ Copied!';
                                                            setTimeout(() => e.target.textContent = '📋 Copy', 2000);
                                                        }}
                                                    >
                                                        📋 Copy
                                                    </button>
                                                </div>
                                                <div className="markdown-content">
                                                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                                        {aiInsights.suggestions}
                                                    </ReactMarkdown>
                                                </div>
                                            </div>
                                        )}

                                        {!aiInsights.description && !aiInsights.pattern && !aiInsights.suggestions && (
                                            <div className="empty-state">
                                                <div className="empty-icon">⏳</div>
                                                <h3>AI Analysis in Progress</h3>
                                                <p>No insights available yet. The AI might be processing or encountered an issue.</p>
                                                <small>Try regenerating the diagrams or check your API key.</small>
                                            </div>
                                        )}
                                    </div>
                                ) : (
                                    <div className="empty-state">
                                        <div className="empty-icon">🤖</div>
                                        <h3>AI Insights Unavailable</h3>
                                        <p>Configure Google Gemini API key to enable AI-powered code analysis.</p>
                                        <small>Get free API key at: https://aistudio.google.com/app/apikey</small>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Fullscreen Modal */}
            {isFullscreen && (
                <div className="fullscreen-container">
                    <div className="fullscreen-header">
                        <div className="fullscreen-title">
                            {activeTab === "flowchart" ? "📊 Flowchart" : activeTab === "workflow" ? "🔄 Workflow" : "🤖 AI Insights"} - Fullscreen View
                        </div>
                        <button className="fullscreen-close" onClick={toggleFullscreen}>
                            ✕ Close
                        </button>
                    </div>
                    <div className="fullscreen-content">
                        <div className="flow-container">
                            {activeTab === "flowchart" ? (
                                <div
                                    ref={fullscreenFlowchartRef}
                                    className="mermaid-diagram"
                                />
                            ) : (
                                <div
                                    ref={fullscreenWorkflowRef}
                                    className="mermaid-diagram"
                                />
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

export default App;
