"""FlowGen HTTP API and local, same-origin workbench."""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from anyio import Semaphore, WouldBlock
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from starlette.staticfiles import StaticFiles

from .inputs import archive_entries, clean_uploads, fail, source_file, upload_files, utf8_size
from .model import LANGUAGES, MAX_ARCHIVE_BYTES, MAX_FILES, MAX_PROJECT_BYTES, AnalysisError
from .project import Project

MAX_REQUEST_BYTES = 14 * 1024 * 1024
Mode = Literal["flowchart", "workflow", "overview"]
ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend" / "public"


class RequestLimits:
    """Cap incoming bodies before the JSON or multipart parser allocates them."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def secure_send(message):
            if message["type"] == "http.response.start":
                message["headers"] = [
                    *message.get("headers", []),
                    (b"x-content-type-options", b"nosniff"),
                    (b"referrer-policy", b"no-referrer"),
                    (
                        b"content-security-policy",
                        b"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob: data:; "
                        b"object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
                    ),
                ]
                if scope["path"].startswith("/api/"):
                    message["headers"].append((b"cache-control", b"no-store"))
            await send(message)

        if scope["method"] != "POST":
            await self.app(scope, receive, secure_send)
            return

        async def too_large():
            await JSONResponse({"detail": "Request exceeds the upload limit."}, status_code=413)(
                scope, receive, secure_send
            )

        length = dict(scope["headers"]).get(b"content-length", b"")
        if length.isdigit() and (len(length) > 12 or int(length) > MAX_REQUEST_BYTES):
            await too_large()
            return

        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message["body"])
            if len(body) > MAX_REQUEST_BYTES:
                await too_large()
                return
            if not message.get("more_body"):
                break

        first = True

        async def replay():
            nonlocal first
            if first:
                first = False
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, secure_send)


class SourceInput(BaseModel):
    path: str = Field(min_length=1, max_length=400)
    content: str
    language: str | None = None


class AnalyzeInput(BaseModel):
    files: list[SourceInput] = Field(min_length=1, max_length=MAX_FILES)
    mode: Mode = "flowchart"
    symbolId: str | None = Field(default=None, max_length=800)


class DiagramNode(BaseModel):
    id: str
    kind: str
    label: str
    path: str | None
    line: int | None
    endLine: int | None
    detail: str | None
    symbolId: str | None


class DiagramEdge(BaseModel):
    source: str
    target: str
    label: str
    kind: str


class Diagram(BaseModel):
    title: str
    mode: Mode
    nodes: list[DiagramNode]
    edges: list[DiagramEdge]
    warnings: list[str]
    symbolId: str | None = None


class Scope(BaseModel):
    id: str
    name: str
    qualifiedName: str
    label: str
    path: str
    line: int
    endLine: int
    entry: str | None
    module: bool


class Diagnostic(BaseModel):
    path: str | None
    line: int | None
    message: str


class ProjectReport(BaseModel):
    files: list[SourceInput]
    symbols: list[Scope]
    diagnostics: list[Diagnostic]
    graph: Diagram | None
    languages: list[str]


class DiagramResponse(BaseModel):
    graph: Diagram


@asynccontextmanager
async def lifespan(app):
    slots = os.environ.get("FLOWGEN_ANALYSIS_SLOTS", "2")
    if slots not in {str(number) for number in range(1, 17)}:
        raise RuntimeError("FLOWGEN_ANALYSIS_SLOTS must be an integer from 1 to 16.")
    app.state.analysis_slots = Semaphore(int(slots))
    yield


app = FastAPI(
    title="FlowGen AI",
    version="2.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)
app.add_middleware(RequestLimits)


@app.exception_handler(AnalysisError)
async def analysis_error(_request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=422)


@app.exception_handler(HTTPException)
async def request_error(_request, exc):
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def invalid_request(_request, exc):
    errors = [{key: error[key] for key in ("loc", "msg", "type")} for error in exc.errors()]
    return JSONResponse({"detail": errors}, status_code=422)


async def run_analysis(request, function, *args):
    slots = request.app.state.analysis_slots
    try:
        slots.acquire_nowait()
    except WouldBlock as error:
        raise HTTPException(
            status_code=503,
            detail="Analysis is busy. Try again shortly.",
            headers={"Retry-After": "2"},
        ) from error
    try:
        return await run_in_threadpool(function, *args)
    finally:
        slots.release()


def analyze_files(payload):
    files, seen = [], set()
    total = 0
    for item in payload.files:
        unit = source_file(item.path, item.content, item.language)
        if unit[0] in seen:
            fail(f"Duplicate file path: {unit[0]}.")
        seen.add(unit[0])
        total += utf8_size(unit[2])
        if total > MAX_PROJECT_BYTES:
            fail("Input exceeds the 2 MiB total source limit.", 413)
        files.append(unit)
    if not any(language in LANGUAGES for _, language, _ in files):
        fail("No supported source files were found.")
    project = Project(files)
    if payload.symbolId is not None:
        return {"graph": project.select(payload.mode, payload.symbolId)}
    return project.report(payload.mode)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "languages": LANGUAGES,
        "limits": {
            "files": MAX_FILES,
            "sourceBytes": MAX_PROJECT_BYTES,
            "archiveBytes": MAX_ARCHIVE_BYTES,
        },
    }


BUSY_RESPONSE = {
    503: {"description": "All analysis slots are busy. Retry after the indicated delay."}
}


@app.post(
    "/api/analyze",
    response_model=ProjectReport | DiagramResponse,
    response_model_exclude_unset=True,
    responses=BUSY_RESPONSE,
)
async def analyze(request: Request, payload: AnalyzeInput):
    return await run_analysis(request, analyze_files, payload)


MULTIPART_REQUEST = {
    "requestBody": {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": ["files"],
                    "properties": {
                        "files": {"type": "array", "items": {"type": "string", "format": "binary"}}
                    },
                }
            }
        },
    }
}


def analyze_upload(items, mode):
    files = archive_entries(items) if isinstance(items, bytes) else clean_uploads(items)
    return Project(files).report(mode)


@app.post(
    "/api/upload",
    response_model=ProjectReport,
    response_model_exclude_unset=True,
    responses=BUSY_RESPONSE,
    openapi_extra=MULTIPART_REQUEST,
)
async def upload(request: Request, mode: Mode = "workflow"):
    async with request.form(max_files=MAX_FILES, max_fields=2, max_part_size=4096) as form:
        items = await upload_files(form)
    return await run_analysis(request, analyze_upload, items, mode)


@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")


app.mount("/assets", StaticFiles(directory=FRONTEND), name="assets")
