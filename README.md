# FlowGen AI

FlowGen AI turns source code into interactive flowcharts and lets you follow calls across a project. Click a node to see its source lines. Open a called function’s flowchart directly from the project workflow.

## Run locally

Install Python 3.11 or newer, clone the repository, and run these commands from its root.

```sh
python -m venv .venv
```

Activate the environment with `source .venv/bin/activate` on macOS or Linux, or `.\.venv\Scripts\Activate.ps1` in Windows PowerShell.

```sh
python -m pip install -r backend/requirements.txt
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --limit-concurrency 24
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). The workbench ships with the API and needs no Node build, model download, or API key.

## Use the workbench

- **Code snippet.** Select a language, paste code, and generate a flowchart. Scope selects a specific function or the file’s top-level code. Use **Load example** for the selected language.
- **Files or project.** Upload a source file to open its flowchart, or choose multiple files, a directory, or a ZIP to explore a workflow. **Workflow** follows statically resolvable calls from the selected entry or function. **Modules** shows source files linked by imports or includes. Select a workflow node and choose **Open flowchart** to see its logic.
- **Read and share.** Select a node to see its original code and line numbers. Fit, zoom, or expand the diagram. Export SVG, PNG, graph JSON, or Mermaid source.

Python, JavaScript, TypeScript, Java, C, and C++ are supported. Call resolution covers common Python imports, JavaScript and TypeScript ES modules, Java class-qualified calls, and project C/C++ headers with same-stem implementation files. All six languages support same-file calls where the analyzer can identify an unambiguous target.

### What the graphs show

Flowcharts model statements, decisions, and loop and function exits. Compound expressions are shown as a single step. Some language-specific constructs are summarized with a dashed node and a diagnostic. Exception edges show possible paths. Workflows show possible calls and their source lines. Runtime order, dynamic dispatch, callbacks scheduled by a framework, generated code, and external dependencies can require runtime or build context. Unresolved calls appear as dashed nodes.

Labels are generated locally by splitting identifiers and preserving acronyms. The source preview retains the original identifier or statement. The workbench sends input to its FlowGen API for static parsing. FlowGen parses source without executing it, contacting an AI provider, or retaining the project after the request. Uploaded source must be UTF-8. The limits are 256 KiB per source file, 2 MiB total source, 120 source files, and 8 MiB for a ZIP. Common dependency and build directories are skipped.

[API contract](backend/API_DOCUMENTATION.md)

## Verify

```sh
python -m pip install -r backend/requirements-dev.txt
python -m playwright install chromium
python -m ruff check backend
python -m ruff format --check backend
python -m pytest backend
```

Set `FLOWGEN_CHROMIUM_CHANNEL=chrome` in the environment to use an installed Google Chrome instead of Playwright’s Chromium. Browser tests launch a loopback server and cover the workbench with the live API.
