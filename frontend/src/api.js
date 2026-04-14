import axios from "axios";

const API_BASE = process.env.REACT_APP_API_URL || "http://127.0.0.1:8000/api";

export async function analyzeCode({ code, file }) {
    const form = new FormData();
    if (file) {
        form.append("file", file);
    } else {
        form.append("code", code || "");
        form.append("filename", "snippet.py");
    }

    const res = await axios.post(`${API_BASE}/analyze`, form, {
        headers: { "Content-Type": "multipart/form-data" },
    });
    return res.data;
}

export async function fetchFlowchart({ code, file }) {
    const form = new FormData();
    if (file) form.append("file", file);
    else { form.append("code", code || ""); form.append("filename", "snippet.py"); }
    const res = await axios.post(`${API_BASE}/flowchart`, form, { headers: { "Content-Type": "multipart/form-data" } });
    return res.data;
}

export async function fetchWorkflow({ code, file }) {
    const form = new FormData();
    if (file) form.append("file", file);
    else { form.append("code", code || ""); form.append("filename", "snippet.py"); }
    const res = await axios.post(`${API_BASE}/workflow`, form, { headers: { "Content-Type": "multipart/form-data" } });
    return res.data;
}
