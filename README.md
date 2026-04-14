# 🎨 FlowGen AI: The Unified Code Visualization Engine

**AI-powered flowchart and workflow generation from source code**

Transform your code into beautiful, interactive diagrams automatically!

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11-blue.svg)
![React](https://img.shields.io/badge/react-18.2-blue.svg)

## ✨ Features

### 🎯 Core Features

- **Multi-Language Support**: Python, JavaScript, Java, C, C++
- **Dual Visualization**: Flowcharts (detailed logic) + Workflows (high-level steps)
- **Three Input Modes**: Code snippet, file upload, or entire project folder
- **Smart Parsing**: AST-based analysis for accurate code understanding
- **Export Options**: JSON, PNG, Mermaid (.mmd) formats

### 🤖 AI-Powered (Optional)

- **Code Descriptions**: Natural language explanations
- **Algorithm Detection**: Auto-identify sorting, searching, recursion, etc.
- **Smart Suggestions**: Code improvement recommendations
- **FREE with Groq API!** (14,400 requests/day)

### 🎨 Modern UI

- Dark theme with gradient accents
- Monaco code editor with syntax highlighting
- Vertical diagram layout
- Fullscreen view
- Responsive design

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 16+
- Git

### Installation

```bash
# Clone the repository
git clone https://github.com/piyush-jaloniya/FlowGen-AI.git
cd FlowGen-AI

# Backend setup
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1  # Windows
# or: source venv/bin/activate  # Linux/Mac

pip install -r requirements.txt
python -m spacy download en_core_web_sm

# Frontend setup
cd ../frontend
npm install

# Start servers
# Terminal 1 - Backend:
cd backend
uvicorn app.main:app --reload

# Terminal 2 - Frontend:
cd frontend
npm start
```

App opens at **<http://localhost:3000>** 🎉

## 🆓 Enable FREE AI Features (Optional)

Get smarter code analysis in 3 minutes!

1. **Get free Groq API key**: <https://console.groq.com/keys>
2. **Create `.env`**:

   ```bash
   cd backend
   copy .env.example .env
   ```

3. **Add your key** to `backend/.env`:

   ```env
   GROQ_API_KEY=gsk_your_key_here
   GROQ_MODEL=llama-3.1-70b-versatile
   ```

4. **Done!** Backend auto-reloads. See AI insights when you generate diagrams.

📖 **Full guide**: [GROQ_SETUP.md](GROQ_SETUP.md)

## 📖 Usage

### 1. Code Snippet Mode

- Select language (Python, JavaScript, Java, C, C++)
- Paste or write code
- Click "Generate Diagrams"

### 2. File Upload Mode

- Click "Upload File"
- Select `.py`, `.js`, `.java`, `.c`, `.cpp` files
- Supports multiple files!

### 3. Project Folder Mode

- ZIP your project folder
- Upload the ZIP file
- Analyzes all code files automatically

## 🎨 Tech Stack

**Frontend:**

- React 18.2
- Monaco Editor (VS Code editor)
- Mermaid.js (diagram rendering)
- Axios (API calls)

**Backend:**

- FastAPI (Python web framework)
- spaCy (NLP for semantic analysis)
- Tree-sitter (C/C++ parsing)
- Esprima (JavaScript parsing)
- Javalang (Java parsing)

**AI/ML (Optional):**

- Groq API (free LLM)
- OpenAI API (alternative)

## 📊 Supported Languages

| Language | Parser | Features |
|----------|--------|----------|
| Python | AST | Functions, control flow, calls |
| JavaScript | Esprima | Functions, ES6 support |
| Java | Javalang | Classes, methods |
| C | Tree-sitter | Functions, headers |
| C++ | Tree-sitter | Classes, templates |

## 🎯 Roadmap

- [ ] More languages (Go, Rust, TypeScript)
- [ ] Interactive diagram editing
- [ ] Collaboration features
- [ ] VS Code extension
- [ ] Custom themes
- [ ] Code complexity metrics

## 📝 Documentation

- [AI Integration Guide](AI_INTEGRATION.md) - Detailed AI setup
- [Quick Groq Setup](GROQ_SETUP.md) - 3-minute free AI setup
- [Features Overview](FEATURES.md) - All features explained

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repo
2. Create a feature branch
3. Submit a pull request

## 📄 License

MIT License - feel free to use for any purpose!

## 🙏 Acknowledgments

- Mermaid.js for beautiful diagrams
- spaCy for NLP capabilities
- Groq for free AI API
- Monaco Editor team

---

**Made with ❤️ for developers who love visual code understanding**

⭐ Star this repo if you find it useful!

# FlowGen-AI
