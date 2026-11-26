"""FlowGen HTTP API and local, same-origin workbench."""

from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
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


app = FastAPI(title="FlowGen AI", version="2.0.0", docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(RequestLimits)


@app.exception_handler(AnalysisError)
async def analysis_error(_request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=422)


@app.exception_handler(HTTPException)
async def request_error(_request, exc):
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)


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


@app.post("/api/analyze")
def analyze(payload: AnalyzeInput):
    return analyze_files(payload)


@app.post("/api/upload")
async def upload(request: Request, mode: Mode = "workflow"):
    async with request.form(max_files=MAX_FILES, max_fields=2, max_part_size=4096) as form:
        items = await upload_files(form)
    files = await run_in_threadpool(
        archive_entries if isinstance(items, bytes) else clean_uploads, items
    )
    return await run_in_threadpool(lambda: Project(files).report(mode))


@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")


app.mount("/assets", StaticFiles(directory=FRONTEND), name="assets")
