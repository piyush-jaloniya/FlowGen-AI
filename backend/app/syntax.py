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
    "abstract_class_declaration",
    "class",
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
PYTHON_COMPREHENSIONS = {
    "list_comprehension",
    "set_comprehension",
    "dictionary_comprehension",
    "generator_expression",
}
PYTHON_TARGET_PATTERNS = {"pattern_list", "tuple_pattern", "list_pattern", "list_splat_pattern"}

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
        binding = field(node.parent, "name", "left", "key")
        if binding is not None and binding.type in {"member_expression", "subscript_expression"}:
            return field(binding, "property", "index")
        return binding
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


def called_lambda(node):
    callee = field(node, "function")
    while callee is not None and callee.type == "parenthesized_expression":
        callee = next((part for part in callee.named_children if part.type != "comment"), None)
    return callee if callee is not None and callee.type == "lambda" else None


def direct_calls(source, root, *, stop=()):
    if root is None:
        return []
    calls = []
    boundaries = FUNCTIONS | CLASSES | set(stop)
    pending = [root]
    while pending:
        node = pending.pop()
        if node.type == "lambda":
            expression = node.parent
            while expression is not None and expression.type == "parenthesized_expression":
                expression = expression.parent
            if (
                expression is not None
                and expression.type == "call"
                and called_lambda(expression) == node
            ):
                body = field(node, "body")
                if body is not None:
                    pending.append(body)
            parameters = field(node, "parameters")
            if parameters is not None:
                pending.append(parameters)
            continue
        if node.type in boundaries:
            continue
        pending.extend(reversed(node.named_children))
        if node.type not in CALLS:
            continue
        if node.type == "call" and called_lambda(node) is not None:
            continue
        name = call_name(source, node)
        if name:
            calls.append(
                Call(re.sub(r"\s*(::|->|\?\.|\.)\s*", ".", name), *source_position(node), node)
            )
    return calls


def irrefutable_python_pattern(pattern):
    if pattern is None:
        return False
    pending = [pattern]
    while pending:
        node = pending.pop()
        if node.type == "_" or (
            node.type == "dotted_name" and not any(child.type == "." for child in node.children)
        ):
            return True
        if node.type in {"case_pattern", "union_pattern"}:
            pending.extend(child for child in node.children if child.is_named or child.type == "_")
        elif node.type == "as_pattern" and node.named_children:
            pending.append(node.named_children[0])
        elif node.type == "tuple_pattern" and not any(child.type == "," for child in node.children):
            pending.extend(node.named_children)
    return False


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


def python_expression_binding(source, node, name):
    offset = node.start_byte
    parent = node.parent
    while parent is not None:
        if parent.type in PYTHON_COMPREHENSIONS:
            if parent.id not in source.comprehension_scopes:
                clauses = [
                    child for child in parent.named_children if child.type == "for_in_clause"
                ]
                iterable = field(clauses[0], "right") if clauses else None
                bound = set()
                pending = [field(clause, "left") for clause in clauses]
                while pending:
                    target = pending.pop()
                    if target is None:
                        continue
                    if target.type == "identifier":
                        bound.add(source.text(target))
                    elif target.type in PYTHON_TARGET_PATTERNS:
                        pending.extend(target.named_children)
                source.comprehension_scopes[parent.id] = (iterable, bound)
            iterable, bound = source.comprehension_scopes[parent.id]
            # Python evaluates the first iterable in the enclosing scope.
            if name in bound and not (
                iterable is not None and iterable.start_byte <= offset < iterable.end_byte
            ):
                return "Name is bound by a comprehension"
        elif parent.type == "lambda":
            body = field(parent, "body")
            parameters = field(parent, "parameters")
            if (
                parameters is not None
                and body is not None
                and body.start_byte <= offset < body.end_byte
            ):
                for parameter in parameters.named_children:
                    binding = parameter
                    if binding.type == "default_parameter":
                        binding = field(parameter, "name")
                    elif binding.type in {"list_splat_pattern", "dictionary_splat_pattern"}:
                        binding = next(iter(parameter.named_children), None)
                    if (
                        binding is not None
                        and binding.type == "identifier"
                        and source.text(binding) == name
                    ):
                        return "Name is bound by a lambda parameter"
        parent = parent.parent
    return None


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
        if source.language in {"c", "cpp"} and node.type == "preproc_include":
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
