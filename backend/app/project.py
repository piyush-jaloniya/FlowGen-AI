"""Index project files and trace resolvable calls from a chosen entry."""

import posixpath
import re
from collections import defaultdict, deque
from functools import cached_property
from pathlib import PurePosixPath

from .flow import FlowBuilder
from .javascript import Import, JSModule, Local, StaticClass
from .model import LANGUAGES, MAX_SYMBOLS, AnalysisError, Graph, humanize
from .syntax import parse_source, python_expression_binding
from .tsconfig import Configs, safe_relative

MAX_TRACE_SYMBOLS = 80
MAX_UNRESOLVED = 45
MAX_EXPORT_LOOKUPS = 256
JS_LANGUAGES = {"javascript", "typescript"}
JS_EXTENSIONS = {extension for language in JS_LANGUAGES for extension in LANGUAGES[language]}
C_LANGUAGES = {"c", "cpp"}
C_HEADERS = {".h", ".hpp", ".hh", ".hxx"}


def stem(path):
    return str(PurePosixPath(path).with_suffix(""))


def joined(base, relative):
    return posixpath.normpath(posixpath.join(base, relative))


def python_names(path):
    parts = PurePosixPath(stem(path)).parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    names = [".".join(parts)]
    if len(parts) > 1 and parts[0] == "src":
        names.append(".".join(parts[1:]))
    return names


class Project:
    def __init__(self, files):
        self.config_files = {path: content for path, lang, content in files if lang == "config"}
        self.configs = Configs(self.config_files)
        self.sources = {
            path: parse_source(path, lang, content)
            for path, lang, content in files
            if lang != "config"
        }
        self.js_modules = {
            path: JSModule(source)
            for path, source in self.sources.items()
            if source.language in JS_LANGUAGES and source.symbols
        }
        self.symbols = {}
        self.by_source = defaultdict(lambda: defaultdict(list))
        self.python_modules = defaultdict(list)
        self.java_classes = defaultdict(list)
        for source in self.sources.values():
            for symbol in source.symbols:
                self.symbols[symbol.id] = symbol
                if not symbol.module:
                    self.by_source[source.path][symbol.qualified_name].append(symbol)
            if source.language == "python":
                for name in python_names(source.path):
                    self.python_modules[name].append(source.path)
            if source.language == "java":
                package = re.search(r"(?m)^\s*package\s+([\w.]+)\s*;", source.content)
                prefix = f"{package.group(1)}." if package else ""
                classes = {
                    symbol.qualified_name.split(".")[0]
                    for symbol in source.symbols
                    if not symbol.module and "." in symbol.qualified_name
                }
                for name in classes:
                    self.java_classes[prefix + name].append(source.path)
        if len(self.symbols) > MAX_SYMBOLS:
            raise AnalysisError(
                f"Project has more than {MAX_SYMBOLS} analyzable symbols. Upload a smaller slice."
            )
        self.apply_c_header_linkage()

    def apply_c_header_linkage(self):
        c_sources = {
            path: unit for path, unit in self.sources.items() if unit.language in C_LANGUAGES
        }
        if not any(unit.c_private_declarations for unit in c_sources.values()):
            return
        direct_headers = {
            path: [
                target
                for target in self.dependency_paths(unit)
                if target in c_sources and PurePosixPath(target).suffix.lower() in C_HEADERS
            ]
            for path, unit in c_sources.items()
        }
        for path, unit in c_sources.items():
            pending = list(direct_headers[path])
            visited = {path}
            declarations = set()
            while pending:
                header = pending.pop()
                if header in visited:
                    continue
                visited.add(header)
                declarations.update(c_sources[header].c_private_declarations)
                pending.extend(direct_headers[header])
            if not declarations:
                continue
            private_names = {name for name, _ in declarations}
            for symbol in unit.symbols:
                if not symbol.module and symbol.c_parameter_types is not None:
                    symbol.local_only |= (
                        symbol.qualified_name in private_names
                        if unit.language == "c"
                        else (symbol.qualified_name, symbol.c_parameter_types) in declarations
                    )

    def relative_python(self, source, module):
        if not module.startswith("."):
            return module
        levels = len(module) - len(module.lstrip("."))
        package = python_names(source.path)[-1].split(".")
        if PurePosixPath(source.path).stem != "__init__":
            package = package[:-1]
        if levels > len(package) + 1:
            return None
        prefix = package[: len(package) + 1 - levels]
        return ".".join(part for part in (*prefix, module.lstrip(".")) if part)

    def js_paths(self, source, module, commonjs):
        if not safe_relative(module):
            return []
        if module.startswith(("./", "../")) or module in {".", ".."}:
            targets = [joined(posixpath.dirname(source.path), module)]
        elif source.language == "typescript":
            targets = self.configs.for_source(source.path).candidates(module)
        else:
            return []
        extension_map = {".js": (".ts", ".tsx"), ".mjs": (".mts",), ".cjs": (".cts",)}
        if source.language == "typescript":
            implicit_extensions = (".ts", ".tsx", ".js", ".jsx")
        else:
            implicit_extensions = (".js",) if commonjs else (".js", ".jsx", ".mjs")
        for target in targets:
            suffix = PurePosixPath(target).suffix
            substitutions = extension_map.get(suffix, ()) if source.language == "typescript" else ()
            candidates = [stem(target) + ext for ext in substitutions] + [target]
            if (
                commonjs
                or not suffix
                or (source.language == "typescript" and suffix not in JS_EXTENSIONS)
            ):
                candidates.extend(target + ext for ext in implicit_extensions)
                candidates.extend(joined(target, "index" + ext) for ext in implicit_extensions)
            for path in candidates:
                found = self.sources.get(path)
                if found is not None and found.language in JS_LANGUAGES:
                    return [path] if path in self.js_modules else []
        return []

    def module_paths(self, source, module):
        if source.language == "python":
            name = self.relative_python(source, module)
            return self.python_modules.get(name, [])
        if source.language == "java":
            return self.java_classes.get(module, [])
        if source.language in C_LANGUAGES:
            target = joined(posixpath.dirname(source.path), module)
            if target in self.sources:
                return [target]
            matches = [
                path for path in self.sources if path == module or path.endswith("/" + module)
            ]
            return matches if len(matches) == 1 else []
        return []

    def dependency_paths(self, source):
        if analyzer := self.js_modules.get(source.path):
            return sorted(
                {
                    path
                    for dependency in analyzer.dependencies
                    for path in self.js_paths(source, dependency.module, dependency.commonjs)
                    if path != source.path
                }
            )
        paths = {
            path
            for dependency in source.dependencies
            for path in self.module_paths(source, dependency)
        }
        if source.language == "python":
            for module, member in source.imports.values():
                name = self.relative_python(source, module)
                if member != "*" and name is not None:
                    submodule = ".".join(part for part in (name, member) if part)
                    paths.update(self.python_modules.get(submodule, ()))
        return sorted(paths - {source.path})

    def find(self, paths, name):
        return [symbol for path in paths for symbol in self.by_source.get(path, {}).get(name, ())]

    @cached_property
    def c_header_links(self):
        headers = defaultdict(list)
        by_name = defaultdict(list)
        by_stem = defaultdict(list)
        includes = defaultdict(set)
        for path, source in self.sources.items():
            if source.language not in C_LANGUAGES:
                continue
            basename = PurePosixPath(path).stem
            if PurePosixPath(path).suffix.lower() in C_HEADERS:
                headers[basename].append(path)
            else:
                by_name[basename].append(path)
                by_stem[stem(path)].append(path)
                for dependency in self.dependency_paths(source):
                    includes[dependency].add(path)

        result = {}
        for basename, paths in headers.items():
            for header in paths:
                linked = includes[header] | set(by_stem[stem(header)])
                parts = PurePosixPath(stem(header)).parts
                for index, part in enumerate(parts[:-1]):
                    if part == "include":
                        counterpart = "/".join((*parts[:index], "src", *parts[index + 1 :]))
                        linked.update(by_stem[counterpart])
                fallback = by_name[basename] if len(paths) == 1 else []
                result[header] = (sorted(linked), fallback)
        return result

    def resolve_js(self, source, call):
        module = self.js_modules[source.path]
        target = module.call_target(call.node)
        if isinstance(target, str):
            return [self.symbols[target]], None
        if not isinstance(target, Import):
            return [], "Value binding or dynamic call target could not be resolved"

        pending = [(source.path, target, ())]
        visited = set()
        targets = {}
        export_lookups = 0
        while pending:
            path, value, remaining = pending.pop()
            index = self.js_modules[path]
            if isinstance(value, Local):
                value = index.root.bindings.get(value.name)
            if isinstance(value, StaticClass) and len(remaining) == 1:
                value = value.methods.get(remaining[0])
                remaining = ()
            elif (
                isinstance(value, StaticClass)
                and not remaining
                and call.node.type == "new_expression"
            ):
                value = value.constructor
            if isinstance(value, str) and not remaining:
                targets[value] = self.symbols[value]
            if not isinstance(value, Import):
                continue
            names = value.names + remaining
            key = (path, value, names)
            if key in visited:
                continue
            visited.add(key)
            export_lookups += 1
            if export_lookups > MAX_EXPORT_LOOKUPS or len(names) > 40:
                return [], "Export resolution budget reached"
            for destination in self.js_paths(self.sources[path], value.module, value.commonjs):
                exported = self.js_modules[destination]
                if names and not value.commonjs:
                    if names[0] in exported.esm:
                        pending.append((destination, exported.esm[names[0]], names[1:]))
                        continue
                    if names[0] != "default" and exported.stars:
                        pending.extend(
                            (destination, Import(item, names), ()) for item in exported.stars
                        )
                        continue
                common_names = (
                    names[1:] if names and not value.commonjs and names[0] == "default" else names
                )
                if common_names and common_names[0] in exported.commonjs:
                    pending.append(
                        (destination, exported.commonjs[common_names[0]], common_names[1:])
                    )
                elif "" in exported.commonjs:
                    pending.append((destination, exported.commonjs[""], common_names))
        if len(targets) == 1:
            return list(targets.values()), None
        if targets:
            return [], "Multiple possible exported targets"
        return [], "External module, unknown export, or unresolved binding"

    def resolve(self, caller, call):
        source = caller.source
        if source.path in self.js_modules:
            return self.resolve_js(source, call)
        name = call.name
        parts = name.split(".")
        if not all(re.fullmatch(r"[\w$]+", part) for part in parts):
            return [], "Dynamic call target"

        if source.language == "python":
            if reason := python_expression_binding(source, call.node, parts[0]):
                return [], reason

        if parts[0] not in {"self", "cls", "this"}:
            local = caller.bindings | source.symbols[0].bindings
            if parts[0] in local:
                return [], "Name is assigned or bound at runtime"

        candidates = []
        if len(parts) == 1:
            if not caller.module:
                scopes = caller.qualified_name.split(".")
                if source.language in C_LANGUAGES or source.language == "java":
                    scopes.pop()
                for length in range(len(scopes), 0, -1):
                    scope = ".".join(scopes[:length])
                    if source.language == "python" and not self.find([source.path], scope):
                        continue
                    owners = self.find([source.path], scope)
                    if any(name in owner.bindings for owner in owners):
                        return [], "Name is assigned or bound at runtime"
                    key = ".".join([*scopes[:length], name])
                    candidates = self.find([source.path], key)
                    if candidates:
                        break
            if not candidates:
                candidates = self.find([source.path], name)
        elif parts[0] in {"self", "cls", "this"} and "." in caller.qualified_name:
            owner = caller.qualified_name.rsplit(".", 1)[0]
            candidates = self.find([source.path], owner + "." + ".".join(parts[1:]))
        elif source.language in C_LANGUAGES:
            candidates = self.find([source.path], name)

        for cut in range(len(parts), 0, -1):
            alias = ".".join(parts[:cut])
            if candidates or alias not in source.imports:
                continue
            module, original = source.imports[alias]
            remainder = parts[cut:]
            paths = self.module_paths(source, module)
            search = ".".join(([original] if original != "*" else []) + remainder)
            if source.language == "java" and len(parts) == 1:
                owner = module.rsplit(".", 1)[-1]
                candidates = self.find(paths, f"{owner}.{search}")
            else:
                candidates = self.find(paths, search)
            if not candidates and source.language == "python" and original != "*" and remainder:
                package = self.relative_python(source, module)
                if package is not None:
                    submodule = ".".join(part for part in (package, original) if part)
                    candidates = self.find(
                        self.python_modules.get(submodule, []), ".".join(remainder)
                    )

        if not candidates and source.language == "java" and len(parts) > 1:
            owner = ".".join(parts[:-1])
            if owner[0].isupper() or owner in self.java_classes:
                package = re.search(r"(?m)^\s*package\s+([\w.]+)\s*;", source.content)
                qualified = f"{package.group(1)}.{owner}" if package else owner
                owners = [path for path in self.java_classes.get(qualified, [])]
                for dependency in source.dependencies:
                    if dependency.rsplit(".", 1)[-1] == owner:
                        owners.extend(self.java_classes.get(dependency, []))
                candidates = self.find(owners, f"{parts[-2]}.{parts[-1]}")
        if not candidates and source.language in C_LANGUAGES:
            dependencies = self.dependency_paths(source)
            for header in dependencies:
                if header in self.c_header_links:
                    linked, fallback = self.c_header_links[header]
                    # A directly included header contributes its definitions to this unit.
                    matches = self.find([header], name) or [
                        symbol for symbol in self.find(linked, name) if not symbol.local_only
                    ]
                    candidates.extend(
                        matches
                        or [symbol for symbol in self.find(fallback, name) if not symbol.local_only]
                    )
            if not candidates and (
                name in source.c_public_declarations
                or any(name in self.sources[path].c_public_declarations for path in dependencies)
            ):
                candidates = [
                    symbol
                    for symbol in self.find(self.sources, name)
                    if symbol.source.language == source.language
                    and not symbol.local_only
                    and PurePosixPath(symbol.source.path).suffix.lower() not in C_HEADERS
                ]

        unique = {symbol.id: symbol for symbol in candidates}
        if len(unique) > 1:
            return [], "Multiple possible targets"
        if unique:
            return list(unique.values()), None
        return [], "External, dynamic, or outside the uploaded files"

    def entries(self):
        return sorted(
            self.symbols.values(),
            key=lambda symbol: (
                symbol.entry is None,
                not symbol.module,
                symbol.source.path,
                symbol.line,
            ),
        )

    def overview(self):
        graph = Graph("Project modules", "overview")
        ids = {}
        for source in self.sources.values():
            if not source.symbols:
                continue
            symbol = source.symbols[0]
            ids[source.path] = graph.node(
                "module",
                source.path,
                path=source.path,
                line=1,
                end_line=1,
                detail=f"{source.language} · {len(source.symbols) - 1} functions",
                symbol=symbol.id,
            )
        for source in self.sources.values():
            if source.path not in ids:
                continue
            for path in self.dependency_paths(source):
                if path in ids:
                    label = "Includes" if source.language in C_LANGUAGES else "Imports"
                    graph.edge(ids[source.path], ids[path], label, "dependency")
        result = graph.public()
        result["warnings"] = []
        return result

    def workflow(self, entry):
        graph = Graph(entry.label, "workflow")
        warnings = set()
        ids = {}
        unresolved = {}
        pending = deque()

        def add(symbol, kind):
            key = symbol.id
            ids[key] = graph.node(
                kind,
                symbol.label,
                path=symbol.source.path,
                line=symbol.line,
                end_line=symbol.end_line,
                detail=symbol.qualified_name,
                symbol=key,
            )
            pending.append(symbol)

        add(entry, "start")
        while pending:
            caller = pending.popleft()
            for call in caller.calls:
                js_module = self.js_modules.get(caller.source.path)
                if js_module is not None and js_module.module_loader(call.node):
                    continue
                candidates, reason = self.resolve(caller, call)
                if candidates:
                    target = candidates[0]
                    if target.id not in ids:
                        if len(ids) >= MAX_TRACE_SYMBOLS:
                            warnings.add(f"Trace is limited to {MAX_TRACE_SYMBOLS} functions.")
                            continue
                        add(target, "call")
                    graph.edge(ids[caller.id], ids[target.id], f"L{call.line}", "call")
                    continue

                key = caller.id, call.name, reason
                if key not in unresolved:
                    if len(unresolved) >= MAX_UNRESOLVED:
                        warnings.add(f"Only the first {MAX_UNRESOLVED} unresolved calls are shown.")
                        continue
                    unresolved[key] = graph.node(
                        "external",
                        humanize(call.name.rsplit(".", 1)[-1]),
                        path=caller.source.path,
                        line=call.line,
                        end_line=call.end_line,
                        detail=f"{call.name} · {reason}",
                    )
                graph.edge(ids[caller.id], unresolved[key], f"L{call.line}", "external")

        result = graph.public()
        result["warnings"] = sorted(warnings)
        return result

    def select(self, mode, symbol_id=None):
        if mode == "overview":
            return self.overview()
        if symbol_id:
            symbol = self.symbols.get(symbol_id)
            if symbol is None:
                raise AnalysisError("The selected symbol is unavailable.")
        else:
            candidates = self.entries()
            if not candidates:
                raise AnalysisError("No valid code was found.")
            symbol = candidates[0]
            if mode == "flowchart" and len(candidates) > 1:
                symbol = next((item for item in candidates if not item.module), symbol)
        graph = FlowBuilder(symbol).build() if mode == "flowchart" else self.workflow(symbol)
        graph["symbolId"] = symbol.id
        return graph

    def report(self, mode):
        graph = None
        diagnostics = [
            *self.configs.diagnostics,
            *(item for source in self.sources.values() for item in source.diagnostics),
        ]
        if self.symbols:
            try:
                graph = self.select(mode)
            except AnalysisError as exc:
                diagnostics.append({"path": None, "line": None, "message": str(exc)})
        return {
            "files": [
                *(source.public() for source in self.sources.values()),
                *(
                    {"path": path, "language": "config", "content": content}
                    for path, content in self.config_files.items()
                ),
            ],
            "symbols": [symbol.public() for symbol in self.entries()],
            "diagnostics": diagnostics,
            "graph": graph,
            "languages": list(LANGUAGES),
        }
