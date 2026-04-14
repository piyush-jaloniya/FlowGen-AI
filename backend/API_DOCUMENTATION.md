# FlowGen AI - API Documentation

## 📚 Overview

FlowGen AI provides a RESTful API for converting source code into interactive flowcharts and workflow diagrams using AI-powered analysis.

**Base URL:** `http://127.0.0.1:8000/api` (development)

**Authentication:** None required (currently public API)

**Rate Limiting:** Yes (varies by endpoint)

---

## 🔑 API Endpoints

### 1. Analyze Code (Combined)

**Endpoint:** `POST /api/analyze`

**Description:** Analyzes code and generates both flowchart and workflow visualizations with optional AI insights.

**Rate Limit:** 20 requests/minute per IP

**Request (JSON):**
```json
{
  "filename": "example.py",
  "content": "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)"
}
```

**Response (200 OK):**
```json
{
  "language": "python",
  "flowchart": {
    "language": "python",
    "mermaid": "flowchart TD\n    Start([Start])\n    ..."
  },
  "workflow": {
    "language": "python",
    "mermaid": "flowchart LR\n    Start([Start])\n    ..."
  },
  "summaries": {
    "fibonacci": "Calculates fibonacci sequence recursively"
  },
  "ai_insights": {
    "description": "This code implements the Fibonacci sequence...",
    "pattern": "Recursion, Dynamic Programming",
    "suggestions": "Consider adding memoization to improve performance..."
  }
}
```

**Error Responses:**
- `400 Bad Request`: Empty code input
- `413 Payload Too Large`: Code exceeds 100,000 characters
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server processing error

---

### 2. Generate Flowchart Only

**Endpoint:** `POST /api/flowchart`

**Description:** Generates only the detailed flowchart visualization.

**Rate Limit:** 20 requests/minute per IP

**Request:** Same as `/api/analyze`

**Response (200 OK):**
```json
{
  "flowchart": {
    "language": "python",
    "mermaid": "flowchart TD\n    Start([Start])\n    ..."
  }
}
```

---

### 3. Generate Workflow Only

**Endpoint:** `POST /api/workflow`

**Description:** Generates only the high-level workflow visualization.

**Rate Limit:** 20 requests/minute per IP

**Request:** Same as `/api/analyze`

**Response (200 OK):**
```json
{
  "workflow": {
    "language": "python",
    "mermaid": "flowchart LR\n    Start([Start])\n    ..."
  }
}
```

---

### 4. Analyze Multiple Files

**Endpoint:** `POST /api/analyze-multiple`

**Description:** Analyzes multiple files or a ZIP archive containing code files.

**Rate Limit:** 10 requests/minute per IP (lower due to expensive operation)

**Request (multipart/form-data):**
```
files: [File1.py, File2.js, File3.java]
```

Or ZIP file:
```
files: [project.zip]
```

**Response (200 OK):**
```json
{
  "processed_files": [
    {"filename": "File1.py", "language": "python", "size": 1234},
    {"filename": "File2.js", "language": "javascript", "size": 567}
  ],
  "total_files": 2,
  "flowchart": {...},
  "workflow": {...},
  "ai_insights": {
    "description": "Multi-file project analysis...",
    "project_summary": "Successfully analyzed 2 file(s) in python, javascript"
  }
}
```

**Validation Limits:**
- Max file size: 10MB per file
- Max ZIP size: 50MB
- Max files in ZIP: 100
- Max code length: 100,000 characters per file

**Error Responses:**
- `413 Payload Too Large`: File/ZIP exceeds size limits

---

## 🌐 Supported Languages

- **Python** (.py)
- **JavaScript** (.js)
- **Java** (.java)
- **C** (.c, .h)
- **C++** (.cpp, .cc, .hpp)

---

## 🔒 Security & Limits

### Input Validation
- **File Size:** 10MB per file, 50MB for ZIP archives
- **Code Length:** 100,000 characters maximum
- **ZIP Files:** Maximum 100 files per archive
- **ZIP Bomb Protection:** Enforced file count limits

### Rate Limiting
| Endpoint | Limit | Window |
|----------|-------|--------|
| `/analyze` | 20 requests | per minute |
| `/flowchart` | 20 requests | per minute |
| `/workflow` | 20 requests | per minute |
| `/analyze-multiple` | 10 requests | per minute |

**Rate Limit Headers:**
```
X-RateLimit-Limit: 20
X-RateLimit-Remaining: 19
X-RateLimit-Reset: 1640000000
```

---

## 🤖 AI Features (Optional)

AI-powered insights are provided when `GEMINI_API_KEY` is configured.

**AI Insights Include:**
- **Description:** Detailed explanation of what the code does
- **Pattern Detection:** Identifies algorithms and design patterns
- **Suggestions:** Code improvement recommendations

**Configuration:**
```env
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```

---

## 📝 Example Usage

### cURL
```bash
curl -X POST "http://127.0.0.1:8000/api/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "test.py",
    "content": "def hello():\n    print(\"Hello, World!\")"
  }'
```

### Python
```python
import requests

response = requests.post(
    "http://127.0.0.1:8000/api/analyze",
    json={
        "filename": "test.py",
        "content": "def hello():\n    print('Hello, World!')"
    }
)

data = response.json()
print(data["flowchart"]["mermaid"])
```

### JavaScript (Axios)
```javascript
const axios = require('axios');

axios.post('http://127.0.0.1:8000/api/analyze', {
  filename: 'test.js',
  content: 'function hello() { console.log("Hello"); }'
})
.then(response => {
  console.log(response.data.workflow.mermaid);
});
```

---

## 🚀 Interactive Documentation

Visit the auto-generated Swagger UI for interactive API testing:

**Swagger UI:** `http://127.0.0.1:8000/docs`

**ReDoc:** `http://127.0.0.1:8000/redoc`

---

## ⚠️ Error Handling

All errors follow this format:
```json
{
  "detail": "Error message description"
}
```

**Common Error Codes:**
- `400`: Bad Request (invalid input)
- `413`: Payload Too Large (size limits exceeded)
- `422`: Validation Error (invalid request format)
- `429`: Too Many Requests (rate limit exceeded)
- `500`: Internal Server Error (server-side issue)

---

## 🔄 CORS Configuration

**Allowed Origins:** Configured via `ALLOWED_ORIGINS` environment variable

**Default:** `http://localhost:3000,http://127.0.0.1:3000`

**Production Example:**
```env
ALLOWED_ORIGINS=https://flowgen.example.com,https://app.example.com
```

---

## 📊 Response Times

Typical response times (without AI):
- Simple code (<100 lines): 100-300ms
- Complex code (100-1000 lines): 300-800ms
- Multiple files: 500-2000ms

With AI enabled, add 1-3 seconds for LLM processing.

---

## 🆘 Support

For issues or questions:
- Check the [README.md](../README.md)
- Review [FEATURES.md](../FEATURES.md)
- See [AI_INTEGRATION.md](../AI_INTEGRATION.md) for AI setup
