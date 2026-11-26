"""Tree-sitter adapters and source-backed project symbols."""

import ast
import re
from functools import lru_cache
from pathlib import PurePosixPath

import tree_sitter_c
import tree_sitter_cpp
import tree_sitter_java
import tree_sitter_javascript
import tree_sitter_python
import tree_sitter_typescript
from tree_sitter import Language, Parser

from .model import MAX_SYMBOLS, AnalysisError, Call, Source, Symbol

FUNCTIONS = {
    "function_definition",
    "function_declaration",
    "generator_function_declaration",
    "method_definition",
    "method_declaration",
    "constructor_declaration",
    "arrow_function",
    "function_expression",
    "generator_function",
}
CLASSES = {
    "class_definition",
    "class_declaration",
    "interface_declaration",
    "record_declaration",
    "enum_declaration",
    "struct_specifier",
    "class_specifier",
    "namespace_definition",
}
CALLS = {
    "call",
    "call_expression",
    "method_invocation",
    "object_creation_expression",
    "new_expression",
}
CONTAINERS = {
    "translation_unit",
    "program",
    "module",
    "class_body",
    "declaration_list",
    "field_declaration_list",
}

GRAMMARS = {
    "python": tree_sitter_python.language,
    "javascript": tree_sitter_javascript.language,
    "typescript": tree_sitter_typescript.language_typescript,
    "tsx": tree_sitter_typescript.language_tsx,
    "java": tree_sitter_java.language,
    "c": tree_sitter_c.language,
    "cpp": tree_sitter_cpp.language,
}


@lru_cache
def grammar(name: str):
    return Language(GRAMMARS[name]())


def field(node, *names):
    if node is not None:
        for name in names:
            value = node.child_by_field_name(name)
            if value is not None:
                return value
    return None


def walk(root, stop=()):
    stack = [root]
    while stack:
        node = stack.pop()
        yield node
        if node.type not in stop:
            stack.extend(reversed(node.named_children))


def source_position(node):
    line = node.start_point.row + 1
    end = node.end_point.row + (
        1 if node.end_point.column or node.end_point.row == node.start_point.row else 0
    )
    return line, max(line, end)


def function_name(node):
    name = field(node, "name")
    if name is not None:
        return name
    current = field(node, "declarator")
    while current is not None:
        if current.type in {
            "identifier",
            "field_identifier",
            "qualified_identifier",
            "operator_name",
            "destructor_name",
        }:
            return current
        current = field(current, "declarator")
    if node.parent and node.parent.type in {
        "variable_declarator",
        "assignment_expression",
        "assignment",
        "pair",
    }:
        return field(node.parent, "name", "left", "key")
    return None


def entry_kind(source, node, name, scope):
    if name == "main" and (
        (not scope and source.language in {"python", "javascript", "typescript", "c", "cpp"})
        or (
            source.language == "java"
            and re.search(r"\bstatic\b", source.text(node).split("{", 1)[0])
        )
    ):
        return "Main"
    if node.parent and node.parent.type == "decorated_definition":
        for decorator in node.parent.named_children:
            if decorator.type == "decorator" and re.search(
                r"\.(get|post|put|patch|delete|route|websocket)\s*\(", source.text(decorator)
            ):
                return "HTTP route"
    if source.language == "java":
        prefix = source.text(node).split("{", 1)[0]
        if re.search(r"@(Get|Post|Put|Patch|Delete|Request)Mapping\b", prefix):
            return "HTTP route"
    return None


def collect_symbols(source):
    root = source.tree.root_node
    is_script = source.language == "python" and any(
        node.type == "if_statement"
        and re.search(
            r"""__name__\s*==\s*['"]__main__['"]""", source.text(field(node, "condition"))
        )
        for node in root.named_children
    )
    source.symbols.append(
        Symbol(
            source,
            "<module>",
            "<module>",
            1,
            source_position(root)[1],
            root,
            root,
            module=True,
            entry="Script entry" if is_script else None,
        )
    )
    stack = [(node, ()) for node in reversed(root.named_children)]
    while stack:
        node, scope = stack.pop()
        if node.type in FUNCTIONS:
            body = field(node, "body")
            label_node = function_name(node)
            label = (
                source.text(label_node)
                if label_node is not None
                else f"anonymous line {node.start_point.row + 1}"
            )
            if body is not None:
                line, end = source_position(node)
                qualified_name = ".".join((*scope, label.replace("::", ".")))
                source.symbols.append(
                    Symbol(
                        source,
                        label,
                        qualified_name,
                        line,
                        end,
                        node,
                        body,
                        entry=entry_kind(source, node, label, scope),
                    )
                )
                if len(source.symbols) > MAX_SYMBOLS:
                    raise AnalysisError(
                        f"{source.path} has more than {MAX_SYMBOLS} analyzable symbols."
                    )
            scope = (*scope, label)
        elif node.type in CLASSES:
            label = source.text(field(node, "name"))
            if label:
                scope = (*scope, label)
        stack.extend((child, scope) for child in reversed(node.named_children))


def call_name(source, node):
    if node.type == "method_invocation":
        qualifier = source.text(field(node, "object"))
        name = source.text(field(node, "name"))
        return ".".join(part for part in (qualifier, name) if part)
    return source.text(field(node, "function", "constructor", "type"))


def direct_calls(source, root, *, stop=()):
    if root is None:
        return []
    calls = []
    for node in walk(root, FUNCTIONS | CLASSES | set(stop)):
        if node.type not in CALLS:
            continue
        name = call_name(source, node)
        if name:
            calls.append(Call(re.sub(r"\s*(::|->|\?\.|\.)\s*", ".", name), *source_position(node)))
    return calls


def python_bindings(source):
    try:
        tree = ast.parse(source.content)
    except (SyntaxError, ValueError, RecursionError):
        return
    functions = {
        (item.lineno, item.name): item
        for item in ast.walk(tree)
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    scopes = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
    comprehensions = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
    for symbol in source.symbols:
        scope = tree if symbol.module else functions.get((symbol.line, symbol.name))
        if scope is None:
            continue
        if not symbol.module:
            symbol.bindings.update(
                item.arg for item in ast.iter_child_nodes(scope.args) if isinstance(item, ast.arg)
            )
        stack = list(scope.body)
        while stack:
            node = stack.pop()
            if isinstance(node, scopes + comprehensions):
                continue
            if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
                symbol.bindings.add(node.id)
            elif isinstance(node, ast.ExceptHandler) and node.name:
                symbol.bindings.add(node.name)
            elif isinstance(node, (ast.Import, ast.ImportFrom)) and not symbol.module:
                symbol.bindings.update(
                    alias.asname or alias.name.split(".")[0] for alias in node.names
                )
            stack.extend(ast.iter_child_nodes(node))


def import_info(source):
    if source.language == "python":
        try:
            tree = ast.parse(source.content)
        except (SyntaxError, ValueError, RecursionError):
            return
        for node in tree.body:
            if isinstance(node, ast.Import):
                for item in node.names:
                    source.dependencies.append(item.name)
                    if item.asname or "." not in item.name:
                        source.imports[item.asname or item.name] = (item.name, "*")
                    else:
                        source.imports[item.name] = (item.name, "*")
            elif isinstance(node, ast.ImportFrom):
                module = "." * node.level + (node.module or "")
                source.dependencies.append(module)
                for item in node.names:
                    if item.name != "*":
                        source.imports[item.asname or item.name] = (module, item.name)
        return

    for node in source.tree.root_node.named_children:
        if source.language in {"javascript", "typescript"} and node.type == "import_statement":
            module = source.text(field(node, "source")).strip("'\"")
            if not module:
                continue
            source.dependencies.append(module)
            for item in walk(node):
                if item.type == "import_specifier":
                    original = source.text(field(item, "name")).strip("'\"")
                    source.imports[source.text(field(item, "alias")) or original] = (
                        module,
                        original,
                    )
                elif item.type == "namespace_import":
                    names = [child for child in item.named_children if child.type == "identifier"]
                    if names:
                        source.imports[source.text(names[0])] = (module, "*")
                elif item.type == "import_clause":
                    names = [child for child in item.named_children if child.type == "identifier"]
                    if names:
                        source.imports[source.text(names[0])] = (module, "default")
        elif source.language in {"c", "cpp"} and node.type == "preproc_include":
            include = source.text(field(node, "path"))
            if include.startswith('"'):
                source.dependencies.append(include.strip('"'))
        elif source.language == "java" and node.type == "import_declaration":
            parts = source.text(node).removeprefix("import").strip().rstrip(";").split()
            if parts:
                module = parts[-1]
                source.dependencies.append(module)
                if len(parts) == 2 and parts[0] == "static" and not module.endswith(".*"):
                    owner, member = module.rsplit(".", 1)
                    source.imports[member] = (owner, member)


def parse_source(path, language, content):
    name = (
        "tsx"
        if language == "typescript" and PurePosixPath(path).suffix.lower() == ".tsx"
        else language
    )
    payload = content.encode("utf-8")
    tree = Parser(grammar(name)).parse(payload)
    source = Source(path, language, content, tree)
    if not tree.root_node.named_children:
        source.diagnostics.append({"path": path, "line": 1, "message": "No code found."})
        return source
    if tree.root_node.has_error:
        for node in walk(tree.root_node):
            if node.is_error or node.is_missing:
                source.diagnostics.append(
                    {
                        "path": path,
                        "line": source_position(node)[0],
                        "message": f"Incomplete syntax. Expected {node.type}."
                        if node.is_missing
                        else "Could not parse this code. Check the syntax and selected language.",
                    }
                )
                if len(source.diagnostics) == 10:
                    break
        return source

    collect_symbols(source)
    import_info(source)
    if language == "python":
        python_bindings(source)
    for symbol in source.symbols:
        symbol.calls = direct_calls(source, symbol.body)

    return source
