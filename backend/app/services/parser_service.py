import ast
import esprima
import javalang
from typing import Dict, Any
from tree_sitter import Parser
from tree_sitter_languages import get_language


class ParserService:
    def __init__(self):
        # initialize dedicated parsers for C / C++
        # Using tree_sitter_languages which properly wraps the language objects
        self.c_parser = Parser()
        self.c_parser.set_language(get_language("c"))

        self.cpp_parser = Parser()
        self.cpp_parser.set_language(get_language("cpp"))
        
    # -------------------------------------------------------------------------
    # Language Detection
    # -------------------------------------------------------------------------
    def detect_language(self, filename: str, content: str) -> str:
        fname = (filename or "").lower()

        # Detect by filename
        if fname.endswith(".py"):
            return "python"
        if fname.endswith(".js"):
            return "javascript"
        if fname.endswith(".java"):
            return "java"
        if fname.endswith(".c"):
            return "c"
        if fname.endswith(".cpp") or fname.endswith(".cc"):
            return "cpp"

        # Detect by content
        if "def " in content and ":" in content:
            return "python"
        if "function " in content:
            return "javascript"
        if "public class " in content or "System.out.println" in content:
            return "java"
        if "#include" in content:
            return "c"
        if "#include" in content and "std::" in content:
            return "cpp"

        return "text"

    # -------------------------------------------------------------------------
    # Dispatcher
    # -------------------------------------------------------------------------
    def parse_code(self, language: str, filename: str, content: str) -> Dict[str, Any]:
        try:
            if language == "python":
                return self._parse_python(filename, content)
            elif language == "javascript":
                return self._parse_javascript(filename, content)
            elif language == "java":
                return self._parse_java(filename, content)
            elif language in ("c", "cpp"):
                return self._parse_c_cpp(language, filename, content)
            else:
                return {"error": f"{language.title()} parsing not supported yet"}
        except Exception as e:
            return {"error": f"{language.title()} parsing failed: {str(e)}"}

    # -------------------------------------------------------------------------
    # PYTHON PARSER (Supports both functions and top-level code)
    # -------------------------------------------------------------------------
    def _parse_python(self, filename: str, content: str) -> Dict[str, Any]:
        try:
            tree = ast.parse(content)
        except Exception as e:
            return {"error": f"AST parsing failed: {str(e)}"}

        funcs = []

        class Visitor(ast.NodeVisitor):
            def __init__(self):
                self.funcs = []
                self.top_calls = []
                self.top_control = []
                self.in_function = False

            def visit_FunctionDef(self, node):
                self.in_function = True
                calls, control = [], []
                for n in ast.walk(node):
                    if isinstance(n, ast.Call):
                        if isinstance(n.func, ast.Name):
                            calls.append(n.func.id)
                        elif isinstance(n.func, ast.Attribute):
                            calls.append(n.func.attr)
                    if isinstance(n, (ast.If, ast.For, ast.While, ast.Try)):
                        control.append(type(n).__name__)
                self.funcs.append({
                    "name": node.name,
                    "args": [a.arg for a in node.args.args],
                    "calls": list(set(calls)),
                    "control_flow": list(set(control)),
                    "docstring": ast.get_docstring(node),
                })
                self.in_function = False

            def visit_Call(self, node):
                # Only collect top-level calls (not inside functions)
                if not self.in_function:
                    if isinstance(node.func, ast.Name):
                        self.top_calls.append(node.func.id)
                    elif isinstance(node.func, ast.Attribute):
                        self.top_calls.append(node.func.attr)
                self.generic_visit(node)

            def visit_For(self, node):
                if not self.in_function:
                    self.top_control.append("For")
                self.generic_visit(node)

            def visit_If(self, node):
                if not self.in_function:
                    self.top_control.append("If")
                self.generic_visit(node)

            def visit_While(self, node):
                if not self.in_function:
                    self.top_control.append("While")
                self.generic_visit(node)

        visitor = Visitor()
        visitor.visit(tree)

        # Create a "main" block for top-level code
        # Add it at the beginning if there are top-level calls or control flows
        if visitor.top_calls or visitor.top_control:
            visitor.funcs.insert(0, {
                "name": "main",
                "args": [],
                "calls": list(set(visitor.top_calls)),
                "control_flow": list(set(visitor.top_control)),
                "docstring": None,
            })

        return {
            "language": "python",
            "functions": visitor.funcs,
            "top_calls": list(set(visitor.top_calls)),
        }

    # -------------------------------------------------------------------------
    # JAVASCRIPT PARSER
    # -------------------------------------------------------------------------
    def _parse_javascript(self, filename: str, content: str) -> Dict[str, Any]:
        tree = esprima.parseScript(content, tolerant=True)
        funcs = []
        all_calls = []

        for node in tree.body:
            if node.type == "FunctionDeclaration":
                name = node.id.name if node.id else "anonymous"
                args = [arg.name for arg in node.params]
                func_calls, func_ctrl = [], []

                for sub in self._walk(node.body):
                    if sub.type == "CallExpression":
                        if hasattr(sub.callee, "name"):
                            func_calls.append(sub.callee.name)
                        elif hasattr(sub.callee, "property"):
                            func_calls.append(sub.callee.property.name)
                    elif sub.type in ["IfStatement", "ForStatement", "WhileStatement"]:
                        func_ctrl.append(sub.type.replace("Statement", ""))

                funcs.append({
                    "name": name,
                    "args": args,
                    "calls": list(set(func_calls)),
                    "control_flow": list(set(func_ctrl)),
                    "docstring": None,
                })
                all_calls += func_calls

        return {"language": "javascript", "functions": funcs, "top_calls": list(set(all_calls))}

    def _walk(self, node):
        """Recursively yield all child nodes for JS."""
        yield node
        for key, value in node.__dict__.items():
            if isinstance(value, list):
                for v in value:
                    if hasattr(v, "__dict__"):
                        yield from self._walk(v)
            elif hasattr(value, "__dict__"):
                yield from self._walk(value)

    # -------------------------------------------------------------------------
    # JAVA PARSER
    # -------------------------------------------------------------------------
    def _parse_java(self, filename: str, content: str) -> Dict[str, Any]:
        tree = javalang.parse.parse(content)
        funcs = []
        all_calls = []

        for path, node in tree.filter(javalang.tree.MethodDeclaration):
            calls, control = [], []
            if not node.body:
                continue
            for _, child in node:
                if isinstance(child, javalang.tree.MethodInvocation):
                    calls.append(child.member)
                elif isinstance(child, (javalang.tree.IfStatement,
                                        javalang.tree.ForStatement,
                                        javalang.tree.WhileStatement)):
                    control.append(type(child).__name__)
            funcs.append({
                "name": node.name,
                "args": [p.type.name for p in node.parameters if hasattr(p.type, "name")],
                "calls": list(set(calls)),
                "control_flow": list(set(control)),
                "docstring": None,
            })
            all_calls += calls

        return {"language": "java", "functions": funcs, "top_calls": list(set(all_calls))}

    # -------------------------------------------------------------------------
    # C / C++ PARSER
    # -------------------------------------------------------------------------
    def _parse_c_cpp(self, language: str, filename: str, content: str) -> Dict[str, Any]:
        parser = self.c_parser if language == "c" else self.cpp_parser
        tree = parser.parse(bytes(content, "utf8"))
        root = tree.root_node

        funcs, calls, control = [], [], []

        def walk(node):
            if node.type == "function_definition":
                func_name = None
                for c in node.children:
                    if c.type == "identifier":
                        func_name = content[c.start_byte:c.end_byte]
                funcs.append({
                    "name": func_name or "unnamed_function",
                    "args": [],
                    "calls": [],
                    "control_flow": [],
                    "docstring": None,
                })
            elif node.type == "call_expression":
                call_name = content[node.children[0].start_byte:node.children[0].end_byte]
                calls.append(call_name)
            elif node.type in ["if_statement", "for_statement", "while_statement"]:
                control.append(node.type.replace("_statement", ""))
            for c in node.children:
                walk(c)

        walk(root)
        for f in funcs:
            f["calls"] = list(set(calls))
            f["control_flow"] = list(set(control))
        return {"language": language, "functions": funcs, "top_calls": list(set(calls))}