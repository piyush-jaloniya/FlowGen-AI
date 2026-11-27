"""Shared source references, labels, and graph format."""

import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath

LANGUAGES = {
    "python": (".py", ".pyw"),
    "javascript": (".js", ".mjs", ".cjs", ".jsx"),
    "typescript": (".ts", ".tsx", ".mts", ".cts"),
    "java": (".java",),
    "c": (".c", ".h"),
    "cpp": (".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx"),
}
MAX_SOURCE_BYTES = 256 * 1024
MAX_PROJECT_BYTES = 2 * 1024 * 1024
MAX_FILES = 120
MAX_ARCHIVE_BYTES = 8 * 1024 * 1024
MAX_SYMBOLS = 400
MAX_GRAPH_NODES = 300


def detect_language(path: str) -> str | None:
    suffix = PurePosixPath(path).suffix.lower()
    return next((lang for lang, extensions in LANGUAGES.items() if suffix in extensions), None)


def humanize(name: str) -> str:
    """Split identifiers while preserving acronyms and digits."""
    name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", name)
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    words = re.findall(r"[^\W_]+", name, re.UNICODE)
    if not words:
        return "Unnamed step"
    return " ".join([words[0][0].upper() + words[0][1:], *words[1:]])


def concise(text: str, limit: int = 78) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


@dataclass
class Call:
    name: str
    line: int
    end_line: int
    node: object


@dataclass
class Symbol:
    source: "Source"
    name: str
    qualified_name: str
    line: int
    end_line: int
    node: object
    body: object
    module: bool = False
    entry: str | None = None
    calls: list[Call] = field(default_factory=list)
    bindings: set[str] = field(default_factory=set)
    local_only: bool = False
    c_parameter_types: tuple | None = None

    @property
    def id(self):
        return (
            f"{self.source.path}:{self.line}:{self.node.start_point.column}:{self.qualified_name}"
        )

    @property
    def label(self):
        return "Top-level code" if self.module else humanize(self.name)

    def public(self):
        return {
            "id": self.id,
            "name": self.name,
            "qualifiedName": self.qualified_name,
            "label": self.label,
            "path": self.source.path,
            "line": self.line,
            "endLine": self.end_line,
            "entry": self.entry,
            "module": self.module,
        }


@dataclass
class Source:
    path: str
    language: str
    content: str
    tree: object
    symbols: list[Symbol] = field(default_factory=list)
    diagnostics: list[dict] = field(default_factory=list)
    imports: dict[str, tuple[str, str]] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    comprehension_scopes: dict = field(default_factory=dict)
    c_public_declarations: set[str] = field(default_factory=set)
    c_private_declarations: set[tuple[str, tuple]] = field(default_factory=set)

    def text(self, node) -> str:
        return node.text.decode("utf-8") if node is not None else ""

    def public(self):
        return {"path": self.path, "language": self.language, "content": self.content}


class AnalysisError(ValueError):
    pass


def diagram_limit_error():
    return AnalysisError(f"Diagram exceeds {MAX_GRAPH_NODES} nodes. Select a smaller scope.")


class Graph:
    def __init__(self, title: str, mode: str, *, node_limit=MAX_GRAPH_NODES):
        self.title = title
        self.mode = mode
        self.nodes = []
        self.edges = []
        self._edges = set()
        self.node_limit = node_limit

    def node(self, kind, label, *, path=None, line=None, end_line=None, detail=None, symbol=None):
        if len(self.nodes) >= self.node_limit:
            if self.node_limit == MAX_GRAPH_NODES:
                raise diagram_limit_error()
            raise AnalysisError(
                "Diagram construction reached its processing limit. Select a smaller scope."
            )
        identifier = f"n{len(self.nodes)}"
        self.nodes.append(
            {
                "id": identifier,
                "kind": kind,
                "label": concise(label),
                "path": path,
                "line": line,
                "endLine": end_line,
                "detail": detail,
                "symbolId": symbol,
            }
        )
        return identifier

    def edge(self, source, target, label="", kind="flow"):
        values = (source, target, label, kind)
        if values not in self._edges:
            self._edges.add(values)
            self.edges.append(dict(zip(("source", "target", "label", "kind"), values)))

    def public(self):
        return {"title": self.title, "mode": self.mode, "nodes": self.nodes, "edges": self.edges}
