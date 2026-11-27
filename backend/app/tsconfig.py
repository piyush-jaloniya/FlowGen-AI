"""Resolve local TypeScript aliases from uploaded JSONC configuration files."""

import json
import posixpath
import re
from dataclasses import dataclass
from pathlib import PurePosixPath

MAX_EXTENDS_DEPTH = 16


def is_tsconfig(path):
    return bool(re.fullmatch(r"tsconfig(?:\.[\w.-]+)?\.json", PurePosixPath(path).name))


def join(base, path):
    return posixpath.normpath(posixpath.join(base, path))


def safe_relative(path):
    return bool(path) and not re.search(r"[\\:\x00-\x1f\x7f]", path) and not path.startswith("/")


def read_jsonc(text):
    """Blank JSONC-only tokens without changing source offsets or line numbers."""
    cleaned = list(text)
    index = 0
    comma = None
    while index < len(text):
        token = text[index]
        if token.isspace():
            index += 1
            continue
        if text.startswith(("//", "/*"), index):
            start = index
            if text[index + 1] == "/":
                index += 2
                while index < len(text) and text[index] not in "\r\n":
                    index += 1
            else:
                end = text.find("*/", index + 2)
                if end == -1:
                    break
                index = end + 2
            for position in range(start, index):
                if text[position] not in "\r\n":
                    cleaned[position] = " "
            continue
        if token in "]}" and comma is not None:
            cleaned[comma] = " "
        comma = index if token == "," else None
        index += 1
        if token == '"':
            while index < len(text):
                if text[index] == "\\":
                    index += 2
                elif text[index] == '"':
                    index += 1
                    break
                else:
                    index += 1
    return json.loads("".join(cleaned))


@dataclass
class Options:
    base_url: str | None = None
    paths: dict | None = None

    def candidates(self, name):
        paths = self.paths or {}
        if name in paths:
            return paths[name]
        wildcard = []
        for pattern, values in paths.items():
            if "*" not in pattern:
                continue
            prefix, suffix = pattern.split("*")
            if (
                name.startswith(prefix)
                and name.endswith(suffix)
                and len(name) >= len(prefix + suffix)
            ):
                missing = name[len(prefix) : len(name) - len(suffix) if suffix else None]
                wildcard.append((len(prefix), values, missing))
        if wildcard:
            _, values, missing = max(wildcard, key=lambda match: match[0])
            return [target.replace("*", missing) for target in values]
        return [join(self.base_url, name)] if self.base_url is not None else []


class Configs:
    def __init__(self, files):
        self.files = frozenset(files)
        self.raw = {}
        self.memo = {}
        self.diagnostics = []
        for path, content in files.items():
            try:
                parsed = read_jsonc(content)
                if not isinstance(parsed, dict):
                    self.warn(path, "Expected a TypeScript configuration object.")
                else:
                    self.raw[path] = parsed
            except json.JSONDecodeError as error:
                self.warn(path, "Could not parse this TypeScript configuration.", error.lineno)
            except (ValueError, RecursionError):
                self.warn(path, "Could not parse this TypeScript configuration.")

        for path in sorted(self.raw):
            self.load(path, ())

    def warn(self, path, message, line=1):
        warning = {"path": path, "line": line, "message": message}
        if warning not in self.diagnostics:
            self.diagnostics.append(warning)

    def load(self, path, ancestors):
        if path in ancestors or len(ancestors) >= MAX_EXTENDS_DEPTH:
            self.warn(path, "TypeScript config inheritance is cyclic or too deep.")
            return None
        if path in self.memo:
            return self.memo[path]
        current = self.raw[path]
        directory = posixpath.dirname(path)
        bases = current.get("extends", [])
        if isinstance(bases, str):
            bases = [bases]
        if not isinstance(bases, list) or len(bases) > MAX_EXTENDS_DEPTH:
            self.warn(path, "Invalid TypeScript config extends list.")
            bases = []
        base_url, paths = None, None
        for base in bases:
            if (
                not isinstance(base, str)
                or not safe_relative(base)
                or not base.startswith(("./", "../"))
            ):
                self.warn(path, "Only uploaded relative TypeScript config inheritance is analyzed.")
                continue
            target = join(directory, base)
            if not target.endswith(".json"):
                target += ".json"
            if target not in self.raw:
                self.warn(path, f"Could not find valid inherited config {base}.")
                continue
            inherited = self.load(target, (*ancestors, path))
            if inherited is None:
                self.memo[path] = None
                return None
            if inherited.base_url is not None:
                base_url = inherited.base_url
            if inherited.paths is not None:
                paths = inherited.paths
        options = current.get("compilerOptions", {})
        if not isinstance(options, dict):
            self.warn(path, "Expected an object for TypeScript compilerOptions.")
            options = {}
        if "baseUrl" in options:
            value = options["baseUrl"]
            if isinstance(value, str) and safe_relative(value):
                base_url = join(directory, value)
            else:
                self.warn(path, "Invalid local TypeScript baseUrl.")
        if "paths" in options:
            values = options["paths"]
            if isinstance(values, dict) and len(values) <= 256:
                paths = {}
                for key, replacements in values.items():
                    if (
                        safe_relative(key)
                        and key.count("*") <= 1
                        and isinstance(replacements, list)
                        and 0 < len(replacements) <= 32
                        and all(
                            isinstance(item, str)
                            and safe_relative(item)
                            and item.count("*") <= key.count("*")
                            for item in replacements
                        )
                    ):
                        paths[key] = [
                            join(base_url if base_url is not None else directory, item)
                            for item in replacements
                        ]
                    else:
                        self.warn(path, "One or more TypeScript path mappings are invalid.")
            else:
                self.warn(path, "Expected a TypeScript paths object with at most 256 mappings.")
        config = Options(base_url, paths)
        self.memo[path] = config
        return config

    def for_source(self, path):
        directory = PurePosixPath(path).parent
        for parent in (directory, *directory.parents):
            name = (parent / "tsconfig.json").as_posix()
            if name in self.files:
                return self.memo.get(name) or Options()
        return Options()
