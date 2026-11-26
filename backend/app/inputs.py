"""Bounded source ingestion without extracting archive members to the filesystem."""

import io
import re
import stat
import zipfile
from pathlib import PurePosixPath

from fastapi import HTTPException
from starlette.datastructures import UploadFile

from .model import (
    LANGUAGES,
    MAX_ARCHIVE_BYTES,
    MAX_FILES,
    MAX_PROJECT_BYTES,
    MAX_SOURCE_BYTES,
    detect_language,
)

IGNORED_DIRS = {
    ".git",
    ".venv",
    ".idea",
    "node_modules",
    "vendor",
    "__pycache__",
    "__MACOSX",
    "dist",
    "build",
    "target",
    "venv",
    "coverage",
}
MAX_ARCHIVE_ENTRIES = 1200


def fail(message, status=400):
    raise HTTPException(status_code=status, detail=message)


def source_path(name):
    name = (name or "").replace("\\", "/")
    parts = name.split("/")
    if not name or len(name) > 400 or any(not p or p in {".", ".."} for p in parts):
        fail("Invalid source path.")
    if re.search(r"[\x00-\x1f\x7f:]", name):
        fail("Invalid source path.")
    return name


def utf8_size(content):
    try:
        return len(content.encode("utf-8"))
    except UnicodeEncodeError:
        fail("Source must use valid UTF-8.")


def source_file(path, content, forced_language=None):
    path = source_path(path)
    language = forced_language or detect_language(path)
    if language not in LANGUAGES:
        fail(f"Unsupported language for {path}.")
    if utf8_size(content) > MAX_SOURCE_BYTES:
        fail(f"{path} exceeds the 256 KiB source limit.", 413)
    return path, language, content


def decode(data, path):
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        fail(f"{path} must be saved as UTF-8.")


def clean_uploads(entries):
    if not entries:
        fail("No supported source files were found.")
    parents = [PurePosixPath(path).parts for path, _ in entries]
    if all(len(parts) > 1 and parts[0] == parents[0][0] for parts in parents):
        root = parents[0][0]
        if root not in {"src", "lib", "app", "test", "tests", "include"} and not any(
            path == root + "/__init__.py" for path, _ in entries
        ):
            entries = [(path.split("/", 1)[1], data) for path, data in entries]
    seen = set()
    result = []
    use_cpp_headers = any(detect_language(path) == "cpp" for path, _ in entries) and not any(
        path.lower().endswith(".c") for path, _ in entries
    )
    for path, data in sorted(entries):
        if path in seen:
            fail(f"Duplicate file path: {path}.")
        seen.add(path)
        language = "cpp" if use_cpp_headers and path.lower().endswith(".h") else None
        result.append(source_file(path, decode(data, path), language))
    return result


def supported(path):
    return detect_language(path) is not None and not (
        set(PurePosixPath(path).parts[:-1]) & IGNORED_DIRS
    )


def archive_entries(data):
    entries = []
    size = 0
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            listing = archive.infolist()
            if len(listing) > MAX_ARCHIVE_ENTRIES:
                fail(f"Archive exceeds {MAX_ARCHIVE_ENTRIES} entries.", 413)
            for entry in listing:
                if entry.is_dir():
                    continue
                path = source_path(entry.orig_filename)
                if not supported(path):
                    continue
                if stat.S_ISLNK(entry.external_attr >> 16):
                    fail("Symbolic links in source archives are unsupported.")
                if entry.flag_bits & 1:
                    fail("Password-protected source archives are unsupported.")
                if len(entries) >= MAX_FILES or entry.file_size > MAX_SOURCE_BYTES:
                    fail("Archive exceeds the source file count or per-file size limit.", 413)
                remaining = MAX_PROJECT_BYTES - size
                if entry.file_size > remaining:
                    fail("Archive exceeds the 2 MiB total source limit.", 413)
                with archive.open(entry) as member:
                    payload = member.read(min(MAX_SOURCE_BYTES, remaining) + 1)
                if len(payload) > min(MAX_SOURCE_BYTES, remaining):
                    fail("Archive exceeds the uncompressed source limit.", 413)
                size += len(payload)
                entries.append((path, payload))
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, EOFError, OSError, ValueError):
        fail("Unable to read this ZIP archive.")
    return clean_uploads(entries)


async def upload_files(form):
    items = form.getlist("files")
    if not items or any(not isinstance(item, UploadFile) for item in items):
        fail("Attach source files, a folder, or one ZIP archive.")
    if len(items) > MAX_FILES:
        fail(f"Upload at most {MAX_FILES} files.", 413)
    zip_items = [item for item in items if (item.filename or "").lower().endswith(".zip")]
    if zip_items:
        if len(items) != 1:
            fail("Upload one ZIP archive at a time.")
        data = await zip_items[0].read(MAX_ARCHIVE_BYTES + 1)
        if len(data) > MAX_ARCHIVE_BYTES:
            fail("ZIP archives must be 8 MiB or smaller.", 413)
        return data

    entries = []
    remaining = MAX_PROJECT_BYTES
    for item in items:
        path = source_path(item.filename)
        if not supported(path):
            continue
        limit = min(remaining, MAX_SOURCE_BYTES)
        payload = await item.read(limit + 1)
        if len(payload) > limit:
            fail("Upload exceeds the 256 KiB per-file or 2 MiB total source limit.", 413)
        remaining -= len(payload)
        entries.append((path, payload))
    return entries
