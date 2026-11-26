"""Build source-level control flow with explicit continuation targets."""

from dataclasses import dataclass, replace

from .model import AnalysisError, Graph, concise, humanize
from .syntax import CLASSES, CONTAINERS, FUNCTIONS, direct_calls, field, source_position

BRANCHES = {"if_statement", "elif_clause"}
FOR_LOOPS = {"for_statement", "for_in_statement", "enhanced_for_statement", "for_range_loop"}
LOOPS = FOR_LOOPS | {"while_statement", "do_statement"}
GROUPS = {"block", "compound_statement", "statement_block", "constructor_body"} | CONTAINERS
RETURNS = {"return_statement", "co_return_statement"}
THROWS = {"raise_statement", "throw_statement", "throw_expression"}
TRIES = {"try_statement", "try_with_resources_statement"}
CASES = {
    "switch_case",
    "switch_default",
    "case_statement",
    "switch_block_statement_group",
    "switch_rule",
}
HANDLERS = {"except_clause", "catch_clause"}
ENDINGS = {"finally_clause", "finally_block"}
IGNORED = {"comment", "line_comment", "block_comment", "empty_statement"}
CALL_BOUNDARIES = (
    BRANCHES | LOOPS | TRIES | {"match_statement", "switch_statement", "switch_expression"}
)


@dataclass(frozen=True)
class Targets:
    return_to: str
    throw_to: str
    break_to: str | None = None
    continue_to: str | None = None


class FlowBuilder:
    def __init__(self, symbol):
        self.symbol = symbol
        self.source = symbol.source
        self.graph = Graph(symbol.label, "flowchart")
        self.warnings = set()

    def add(self, kind, label, node):
        return self.graph.node(
            kind,
            label,
            path=self.source.path,
            line=source_position(node)[0],
            end_line=source_position(node)[1],
            detail=concise(self.source.text(node), 350),
        )

    def statements(self, nodes, following, targets):
        for node in reversed(nodes):
            following = self.statement(node, following, targets)
        return following

    def body(self, node, following, targets):
        if node is None:
            return following
        if node.type in GROUPS or node.type in {"else_clause", "finally_clause", "finally_block"}:
            return self.statements(node.named_children, following, targets)
        return self.statement(node, following, targets)

    def condition(self, node, following, targets):
        condition = field(node, "condition")
        text = self.source.text(condition).strip()
        decision = self.add("decision", text or "Evaluate condition", condition or node)
        yes = self.body(field(node, "consequence", "body"), following, targets)
        no = following
        for alternative in reversed(node.children_by_field_name("alternative")):
            no = (
                self.condition(alternative, no, targets)
                if alternative.type == "elif_clause"
                else self.body(alternative, following, targets)
            )
        self.graph.edge(decision, yes, "True", "branch")
        self.graph.edge(decision, no, "False", "branch")
        return decision

    def loop(self, node, following, targets):
        condition = field(node, "condition")
        if condition is not None and condition.type == "empty_statement":
            condition = None
        alternative = field(node, "alternative")
        body = field(node, "body")
        right = field(node, "right", "value")
        left = field(node, "left", "name", "declarator")
        iterator = right is not None and node.type in FOR_LOOPS
        init = node.children_by_field_name("initializer") or node.children_by_field_name("init")
        update = node.children_by_field_name("update") or node.children_by_field_name("increment")
        if iterator:
            left_name = self.source.text(left)
            if node.type == "for_range_loop":
                left_name = self.source.text(field(node, "declarator"))
            label = f"Next {left_name or 'item'} in {self.source.text(right)}?"
        else:
            label = self.source.text(condition) or "Repeat"
        check = self.add("decision", label, condition or node)
        repeat = self.statements(update, check, targets)
        loop_targets = replace(targets, break_to=following, continue_to=repeat)
        enter = self.body(body, repeat, loop_targets)
        self.graph.edge(check, enter, "Next item" if iterator else "True", "branch")
        if iterator or condition is not None:
            exit_path = self.body(alternative, following, targets)
            self.graph.edge(check, exit_path, "Exhausted" if iterator else "False", "branch")
        if node.type == "do_statement":
            return enter
        return self.statements(init, check, targets)

    def match(self, node, following, targets):
        subject = field(node, "subject")
        select = self.add(
            "process", f"Match {self.source.text(subject) or 'subject'}", subject or node
        )
        block = field(node, "body")
        clauses = [part for part in (block or node).named_children if part.type == "case_clause"]
        first = following
        for clause in reversed(clauses):
            pattern = next(
                (part for part in clause.named_children if part.type == "case_pattern"), None
            )
            guard = field(clause, "guard")
            pattern_text = self.source.text(pattern)
            body = self.body(field(clause, "consequence", "body"), following, targets)
            decision = self.add(
                "decision", f"Case {pattern_text} {self.source.text(guard)}", clause
            )
            self.graph.edge(decision, body, "Match", "branch")
            if pattern_text != "_" or guard is not None:
                self.graph.edge(decision, first, "No match", "branch")
            first = decision
        self.graph.edge(select, first)
        return select

    def switch(self, node, following, targets):
        body = field(node, "body")
        groups = [item for item in body.named_children if item.type in CASES] if body else []
        if not groups:
            return self.opaque(node, following)
        subject = field(node, "condition", "value")
        decision = self.add("decision", f"Switch {self.source.text(subject)}", subject or node)
        group_targets = replace(targets, break_to=following)
        next_group = following
        destinations = []
        for group in reversed(groups):
            value = field(group, "value")
            label_node = next(
                (child for child in group.named_children if child.type == "switch_label"), None
            )
            statements = [
                child
                for child in group.named_children
                if child != value and child != label_node and child.type not in IGNORED
            ]
            label = (
                self.source.text(label_node)
                if label_node
                else (f"case {self.source.text(value)}" if value is not None else "default")
            )
            case_node = self.add("process", label, label_node or value or group)
            continuation = following if group.type == "switch_rule" else next_group
            self.graph.edge(case_node, self.statements(statements, continuation, group_targets))
            destinations.append((case_node, label))
            next_group = case_node
        for target, label in reversed(destinations):
            self.graph.edge(decision, target, concise(label, 34), "branch")
        if not any(label.startswith("default") for _, label in destinations):
            self.graph.edge(decision, following, "No match", "branch")
        return decision

    def try_statement(self, node, following, targets):
        parts = node.named_children
        handlers = [child for child in parts if child.type in HANDLERS]
        final = next((child for child in parts if child.type in ENDINGS), None)
        final_paths = {}

        def cleanup(target):
            if final is None or target is None:
                return target
            if target not in final_paths:
                final_paths[target] = self.body(final, target, targets)
            return final_paths[target]

        after = cleanup(following)
        outer = Targets(
            cleanup(targets.return_to),
            cleanup(targets.throw_to),
            cleanup(targets.break_to),
            cleanup(targets.continue_to),
        )
        alternate = next((child for child in parts if child.type == "else_clause"), None)
        success = self.body(alternate, after, outer)
        dispatch = outer.throw_to
        if handlers:
            dispatch = self.add("decision", "Which handler matches?", handlers[0])
            catch_all = False
            for handler in handlers:
                contents = field(handler, "body")
                if contents is None:
                    contents = next(
                        (child for child in handler.named_children if child.type in GROUPS), None
                    )
                label = (
                    self.source.text(handler).splitlines()[0].split("{", 1)[0].strip().rstrip(":")
                )
                binding = field(handler, "value", "parameter")
                parameters = field(handler, "parameters")
                catch_all = (
                    catch_all
                    or (
                        self.source.language == "cpp"
                        and parameters is not None
                        and any(child.type == "..." for child in parameters.children)
                    )
                    or (self.source.language == "python" and binding is None)
                    or (
                        self.source.language in {"javascript", "typescript"}
                        and handler.type == "catch_clause"
                    )
                )
                self.graph.edge(
                    dispatch,
                    self.body(contents, after, outer),
                    concise(self.source.text(binding) or label, 38),
                    "exception",
                )
            if not catch_all:
                self.graph.edge(dispatch, outer.throw_to, "Uncaught", "exception")
        start = self.add("process", "Try", node)
        restricted = replace(outer, throw_to=dispatch)
        attempt = self.body(field(node, "body"), success, restricted)
        self.graph.edge(start, attempt)
        self.graph.edge(start, dispatch, "Possible exception", "exception")
        if node.type == "try_with_resources_statement":
            self.warnings.add("Implicit closing of try-with-resources is summarized.")
        return start

    def opaque(self, node, following):
        label = humanize(node.type.removesuffix("_statement"))
        self.warnings.add(f"{label} is summarized as one step. Its internal paths are omitted.")
        result = self.add("opaque", label, node)
        self.graph.edge(result, following, "Abstract continuation")
        return result

    def statement(self, node, following, targets):
        kind = node.type
        if kind in IGNORED:
            return following
        if kind in GROUPS:
            return self.body(node, following, targets)
        if kind in BRANCHES:
            return self.condition(node, following, targets)
        if kind in LOOPS:
            return self.loop(node, following, targets)
        if kind in TRIES:
            return self.try_statement(node, following, targets)
        if kind == "match_statement":
            return self.match(node, following, targets)
        if kind in {"switch_statement", "switch_expression"}:
            return self.switch(node, following, targets)
        if kind in RETURNS:
            current = self.add("control", self.source.text(node).rstrip(";"), node)
            self.graph.edge(current, targets.return_to, "Return")
            return current
        if kind in THROWS:
            current = self.add("control", self.source.text(node).rstrip(";"), node)
            self.graph.edge(current, targets.throw_to, "Exception", "exception")
            return current
        if kind in {"break_statement", "continue_statement"}:
            expected = "break" if kind == "break_statement" else "continue"
            target = targets.break_to if expected == "break" else targets.continue_to
            if target is None or self.source.text(node).rstrip(";").strip() != expected:
                return self.opaque(node, following)
            current = self.add("control", expected.capitalize(), node)
            self.graph.edge(
                current, target, "Exit loop or switch" if expected == "break" else "Next iteration"
            )
            return current
        if kind in {
            "goto_statement",
            "labeled_statement",
            "with_statement",
            "synchronized_statement",
            "preproc_if",
            "preproc_ifdef",
            "preproc_elif",
            "assert_statement",
            "yield_statement",
        }:
            return self.opaque(node, following)
        if kind in FUNCTIONS or kind in CLASSES or kind == "decorated_definition":
            declaration = field(node, "definition") if kind == "decorated_definition" else node
            name = self.source.text(field(declaration, "name", "declarator")).split("(", 1)[0]
            current = self.add("process", f"Define {name}" if name else "Define symbol", node)
            self.graph.edge(current, following)
            return current
        calls = direct_calls(self.source, node, stop=CALL_BOUNDARIES)
        code = self.source.text(node).rstrip(";")
        if any(
            call.name in {"print", "input", "printf", "scanf", "console.log", "System.out.println"}
            for call in calls
        ):
            current = self.add("io", code, node)
        elif len(calls) == 1 and code.strip().startswith(calls[0].name + "("):
            label = humanize(calls[0].name.rsplit(".", 1)[-1])
            current = self.add("call", label, node)
        else:
            current = self.add("process", code, node)
        self.graph.edge(current, following)
        return current

    def build(self):
        start = self.add("start", f"Start · {self.symbol.label}", self.symbol.node)
        normal = self.graph.node("end", "End")
        thrown = self.graph.node("end", "Uncaught exception")
        targets = Targets(normal, thrown)
        try:
            if self.symbol.node.type == "arrow_function" and self.symbol.body.type not in GROUPS:
                expression = self.symbol.body
                body = self.add("control", f"Return {self.source.text(expression)}", expression)
                self.graph.edge(body, normal, "Return")
            else:
                body = self.body(self.symbol.body, normal, targets)
        except RecursionError as exc:
            raise AnalysisError("The code is nested too deeply to diagram.") from exc
        self.graph.edge(start, body)
        reachable = {start}
        outgoing = {}
        for edge in self.graph.edges:
            outgoing.setdefault(edge["source"], []).append(edge["target"])
        pending = [start]
        while pending:
            for target in outgoing.get(pending.pop(), []):
                if target not in reachable:
                    reachable.add(target)
                    pending.append(target)
        result = self.graph.public()
        result["nodes"] = [node for node in result["nodes"] if node["id"] in reachable]
        result["edges"] = [edge for edge in result["edges"] if edge["source"] in reachable]
        result["warnings"] = sorted(self.warnings)
        return result
