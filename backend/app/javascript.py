"""Static value bindings and exports for JavaScript and TypeScript."""

import ast
from dataclasses import dataclass, field

from .syntax import CALLS, CLASSES, FUNCTIONS
from .syntax import field as child

DECLARATIONS = {"function_declaration", "generator_function_declaration"}
SCOPES = {"statement_block", "switch_body", "for_statement", "for_in_statement", "catch_clause"}
PATTERNS = {"array_pattern", "object_pattern", "formal_parameters", "rest_pattern"}
NAMES = {"identifier", "shorthand_property_identifier_pattern"}
WRAPPERS = {
    "parenthesized_expression",
    "as_expression",
    "satisfies_expression",
    "non_null_expression",
}


@dataclass(frozen=True)
class Import:
    module: str
    names: tuple[str, ...] = ()
    commonjs: bool = False


@dataclass(frozen=True)
class Local:
    name: str


@dataclass
class StaticClass:
    methods: dict
    constructor: str | None = None


@dataclass
class Scope:
    parent: "Scope | None" = None
    function: bool = False
    bindings: dict = field(default_factory=dict)
    initializers: dict = field(default_factory=dict)
    duplicates: set = field(default_factory=set)

    def get(self, name):
        scope = self
        while scope is not None:
            if name in scope.bindings:
                return scope
            scope = scope.parent
        return None

    def declare(self, name, value=None, initializer=None):
        if name in self.bindings:
            self.bindings[name] = None
            self.duplicates.add(name)
        else:
            self.bindings[name] = value
            if initializer is not None:
                self.initializers[name] = initializer

    def function_scope(self):
        scope = self
        while not scope.function and scope.parent is not None:
            scope = scope.parent
        return scope


def unwrap(node):
    while node is not None and node.type in WRAPPERS and node.named_child_count:
        node = node.named_children[0]
    return node


def string_value(node):
    if node is None or node.type != "string":
        return None
    try:
        result = ast.literal_eval(node.text.decode("utf-8"))
    except (ValueError, SyntaxError, RecursionError):
        return None
    return result if isinstance(result, str) else None


def pattern_names(node):
    pending = [node]
    while pending:
        item = pending.pop()
        if item is None:
            continue
        if item.type in NAMES:
            yield item.text.decode("utf-8")
        elif item.type in PATTERNS:
            pending.extend(reversed(item.named_children))
        elif item.type == "pair_pattern":
            pending.append(child(item, "value"))
        elif item.type in {"assignment_pattern", "object_assignment_pattern"}:
            pending.append(child(item, "left"))
        elif item.type in {"required_parameter", "optional_parameter"}:
            pending.append(child(item, "pattern", "name"))


def text(node):
    return node.text.decode("utf-8") if node is not None else ""


def property_name(node):
    if node is not None and node.type in {
        "identifier",
        "property_identifier",
        "shorthand_property_identifier",
    }:
        return text(node)
    return string_value(node)


def member(node):
    if node is not None and node.type in {"member_expression", "subscript_expression"}:
        prop = child(node, "property", "index")
        if node.type == "subscript_expression":
            return child(node, "object"), string_value(prop)
        return child(node, "object"), property_name(prop)
    return None, None


class JSModule:
    def __init__(self, source):
        self.root = Scope(function=True)
        self.scopes = {}
        self.nodes = {symbol.node.id: symbol.id for symbol in source.symbols if not symbol.module}
        self.dependencies = set()
        self.esm = {}
        self.commonjs = {}
        self.stars = []
        self.cjs_replaced = False
        calls = []
        pending = [(node, self.root) for node in reversed(source.tree.root_node.named_children)]
        writes = []
        declarations = []
        exports = []
        while pending:
            node, scope = pending.pop()
            kind = node.type
            if kind in CALLS:
                self.scopes[node.id] = scope
                calls.append((node, scope))
            if kind in FUNCTIONS:
                name = child(node, "name")
                if kind in DECLARATIONS and name is not None:
                    scope.declare(text(name), self.nodes.get(node.id))
                scope = Scope(scope, function=True)
                if kind in {"function_expression", "generator_function"} and name is not None:
                    scope.declare(text(name), self.nodes.get(node.id))
                for parameter in pattern_names(child(node, "parameters", "parameter")):
                    scope.declare(parameter)
            elif kind in SCOPES:
                scope = Scope(scope)
                if kind == "catch_clause":
                    for parameter in pattern_names(child(node, "parameter")):
                        scope.declare(parameter)
                if kind == "for_in_statement":
                    keyword = child(node, "kind")
                    if text(keyword) in {"let", "const", "var"}:
                        owner = scope if text(keyword) != "var" else scope.function_scope()
                        for name in pattern_names(child(node, "left")):
                            owner.declare(name)
                    else:
                        writes.append((scope, child(node, "left")))
            elif kind in CLASSES:
                name = child(node, "name")
                if kind in {"class_declaration", "abstract_class_declaration"}:
                    if name is not None:
                        scope.declare(text(name), self.static_class(node), node.end_byte)
                scope = Scope(scope)
                if kind == "class" and name is not None:
                    scope.declare(text(name), self.static_class(node))
            elif kind == "variable_declarator":
                owner = (
                    scope.function_scope() if node.parent.type == "variable_declaration" else scope
                )
                name_node = child(node, "name")
                value = unwrap(child(node, "value"))
                known = self.nodes.get(value.id) if value is not None else None
                if value is not None and value.type == "class":
                    known = self.static_class(value)
                for name in pattern_names(name_node):
                    owner.declare(
                        name, known if name_node.type == "identifier" else None, node.end_byte
                    )
                declarations.append((owner, scope, name_node, value))
            elif kind == "import_statement" and scope is self.root:
                self.read_import(node)
            elif kind == "export_statement" and scope is self.root:
                exports.append(node)
            elif kind in {
                "assignment_expression",
                "augmented_assignment_expression",
                "update_expression",
            }:
                target = child(node, "left", "argument")
                writes.append((scope, target))
                if (
                    scope is self.root
                    and node.parent.type == "expression_statement"
                    and (node.parent.parent.type == "program")
                ):
                    exports.append(node)
            pending.extend((item, scope) for item in reversed(node.named_children))

        reassigned = set()
        for scope, target in writes:
            for name in pattern_names(target):
                owner = scope.get(name) or self.root
                owner.bindings[name] = None
                reassigned.add((id(owner), name))
            while target is not None:
                base, _ = member(target)
                if base is None:
                    break
                target = base
            if target is not None and target.type == "identifier":
                owner = scope.get(text(target))
                if owner:
                    owner.bindings[text(target)] = None
                    reassigned.add((id(owner), text(target)))

        for owner, scope, pattern, value in declarations:
            imported = self.require_ref(value, scope)
            if imported is None:
                continue
            self.dependencies.add(Import(imported.module, commonjs=True))
            if pattern.type == "identifier":
                aliases = [(text(pattern), imported.names)]
            elif pattern.type == "object_pattern" and not imported.names:
                aliases = []
                for item in pattern.named_children:
                    if item.type == "pair_pattern":
                        key, binding = property_name(child(item, "key")), child(item, "value")
                        if key and binding is not None and binding.type == "identifier":
                            aliases.append((text(binding), (key,)))
                    elif item.type == "shorthand_property_identifier_pattern":
                        aliases.append((text(item), (text(item),)))
            else:
                continue
            for name, names in aliases:
                if name not in owner.duplicates and (id(owner), name) not in reassigned:
                    owner.bindings[name] = Import(imported.module, names, commonjs=True)

        for node, scope in calls:
            if imported := self.require_ref(node, scope):
                self.dependencies.add(Import(imported.module, commonjs=True))

        for node in exports:
            if node.type == "export_statement":
                self.read_export(node)
            else:
                self.read_commonjs_export(node)

    def read_import(self, node):
        module = string_value(child(node, "source"))
        if not module or any(item.type == "type" for item in node.children):
            return
        self.dependencies.add(Import(module))
        clause = next((item for item in node.named_children if item.type == "import_clause"), None)
        for item in clause.named_children if clause else ():
            if item.type == "identifier":
                self.root.declare(text(item), Import(module, ("default",)))
            elif item.type == "namespace_import":
                name = next(
                    (part for part in item.named_children if part.type == "identifier"), None
                )
                if name is not None:
                    self.root.declare(text(name), Import(module))
            elif item.type == "named_imports":
                for specifier in item.named_children:
                    if specifier.type != "import_specifier" or any(
                        part.type == "type" for part in specifier.children
                    ):
                        continue
                    original = property_name(child(specifier, "name"))
                    alias = text(child(specifier, "alias")) or original
                    if original and alias:
                        self.root.declare(alias, Import(module, (original,)))

    def require_ref(self, node, scope):
        node = unwrap(node)
        names = []
        while node is not None:
            base, key = member(node)
            if base is None:
                break
            if key is None:
                return None
            names.append(key)
            node = unwrap(base)
        if (
            node is not None
            and node.type == "call_expression"
            and text(child(node, "function")) == "require"
            and scope.get("require") is None
        ):
            args = child(node, "arguments")
            module = (
                string_value(args.named_children[0])
                if args and args.named_child_count == 1
                else None
            )
            if module:
                return Import(module, tuple(reversed(names)), commonjs=True)
        return None

    def value(self, node):
        node = unwrap(node)
        if node is None:
            return None
        if node.id in self.nodes:
            return self.nodes[node.id]
        if node.type in {"identifier", "shorthand_property_identifier"}:
            return Local(text(node))
        if node.type in CLASSES | {"class"}:
            return self.static_class(node)
        return self.require_ref(node, self.root)

    def static_class(self, node):
        methods = {}
        constructor = None
        body = child(node, "body")
        for item in body.named_children if body else ():
            if item.type != "method_definition":
                continue
            modifiers = {part.type for part in item.children if not part.is_named}
            name = property_name(child(item, "name"))
            if name and "static" in modifiers:
                methods[name] = (
                    self.nodes.get(item.id)
                    if (name not in methods and not modifiers & {"get", "set"})
                    else None
                )
            elif name == "constructor":
                constructor = self.nodes.get(item.id)
        return StaticClass(methods, constructor)

    def read_export(self, node):
        if any(item.type == "type" for item in node.children):
            return
        module = string_value(child(node, "source"))
        if module:
            self.dependencies.add(Import(module))
        declaration = child(node, "declaration")
        value = child(node, "value")
        if any(item.type == "default" for item in node.children):
            name = child(declaration, "name")
            self.esm["default"] = Local(text(name)) if name else self.value(declaration or value)
        elif declaration is not None:
            if declaration.type in DECLARATIONS | {
                "class_declaration",
                "abstract_class_declaration",
            }:
                name = text(child(declaration, "name"))
                if name:
                    self.esm[name] = Local(name)
            elif declaration.type in {"lexical_declaration", "variable_declaration"}:
                for declarator in declaration.named_children:
                    for name in pattern_names(child(declarator, "name")):
                        self.esm[name] = Local(name)
        else:
            clause = next(
                (
                    item
                    for item in node.named_children
                    if item.type in {"export_clause", "namespace_export"}
                ),
                None,
            )
            if clause is not None and clause.type == "export_clause":
                for specifier in clause.named_children:
                    if specifier.type != "export_specifier" or any(
                        item.type == "type" for item in specifier.children
                    ):
                        continue
                    original = property_name(child(specifier, "name"))
                    alias = property_name(child(specifier, "alias")) or original
                    if alias and original:
                        self.esm[alias] = Import(module, (original,)) if module else Local(original)
            elif clause is not None and module:
                name = property_name(clause.named_children[-1]) if clause.named_children else None
                if name:
                    self.esm[name] = Import(module)
            elif module and any(item.type == "*" for item in node.children):
                self.stars.append(module)

    def read_commonjs_export(self, node):
        target = child(node, "left")
        base, key = member(target)
        replacement = text(base) == "module" and key == "exports"
        if not replacement:
            owner, prop = member(base)
            alias = text(base) == "exports" and self.root.get("exports") is None
            direct = (
                text(owner) == "module" and prop == "exports" and self.root.get("module") is None
            )
            if not key or not (direct or (alias and not self.cjs_replaced)):
                return
        elif self.root.get("module") is not None:
            return

        right = unwrap(child(node, "right"))
        if replacement:
            self.commonjs.clear()
            self.cjs_replaced = True
            if right is None or right.type != "object":
                self.commonjs[""] = self.value(right)
                return
            for prop in right.named_children:
                name = property_name(child(prop, "key", "name")) or property_name(prop)
                if name:
                    self.commonjs[name] = self.value(child(prop, "value") or prop)
                elif prop.type == "spread_element":
                    self.commonjs.clear()
        elif node.type == "augmented_assignment_expression":
            self.commonjs[key] = None
        else:
            self.commonjs[key] = self.value(right)

    def call_target(self, node):
        scope = self.scopes.get(node.id, self.root)
        callee = unwrap(child(node, "function", "constructor"))
        imported = self.require_ref(callee, scope)
        if imported:
            return imported
        members = []
        while callee is not None:
            base, key = member(callee)
            if base is None:
                break
            if key is None:
                return None
            members.append(key)
            callee = unwrap(base)
        if callee is None:
            return None
        if callee.id in self.nodes and not members:
            return self.nodes[callee.id]
        if callee.type != "identifier":
            return None
        name = text(callee)
        owner = scope.get(name)
        if (
            owner is not None
            and owner.function_scope() is scope.function_scope()
            and node.start_byte < owner.initializers.get(name, -1)
        ):
            return None
        value = owner.bindings[name] if owner is not None else None
        if isinstance(value, Import):
            return Import(value.module, value.names + tuple(reversed(members)), value.commonjs)
        if isinstance(value, StaticClass):
            if len(members) == 1:
                return value.methods.get(members[0])
            return value.constructor if not members and node.type == "new_expression" else None
        return value if not members else None

    def module_loader(self, node):
        return self.require_ref(node, self.scopes.get(node.id, self.root)) is not None
