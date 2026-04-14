import ast
import esprima
import javalang
from typing import Dict, Any
from tree_sitter import Parser
from tree_sitter_languages import get_language
from .cache_service import cached_parse


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
    @cached_parse
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
    # Helper Methods
    # -------------------------------------------------------------------------
    def _ast_to_code(self, node) -> str:
        """Convert an AST node back to source code string."""
        try:
            # Python 3.9+ has ast.unparse
            import sys
            if sys.version_info >= (3, 9):
                return ast.unparse(node)
            else:
                # Fallback for older Python versions
                import astor
                return astor.to_source(node).strip()
        except:
            # If all else fails, return a generic representation
            return str(type(node).__name__)

    def _extract_python_body(self, body_nodes) -> list:
        """Extract detailed body information from Python AST nodes."""
        statements = []
        
        for node in body_nodes:
            if isinstance(node, ast.If):
                # Extract if-elif-else chain
                if_chain = self._extract_if_chain(node)
                statements.append(if_chain)
            elif isinstance(node, ast.For):
                statements.append({
                    "type": "for_loop",
                    "target": self._ast_to_code(node.target),
                    "iter": self._ast_to_code(node.iter),
                    "body": self._extract_python_body(node.body)
                })
            elif isinstance(node, ast.While):
                statements.append({
                    "type": "while_loop",
                    "condition": self._ast_to_code(node.test),
                    "body": self._extract_python_body(node.body)
                })
            elif isinstance(node, ast.Return):
                statements.append({
                    "type": "return",
                    "value": self._ast_to_code(node.value) if node.value else None
                })
            elif isinstance(node, ast.Assign):
                statements.append({
                    "type": "assignment",
                    "targets": [self._ast_to_code(t) for t in node.targets],
                    "value": self._ast_to_code(node.value)
                })
            elif isinstance(node, ast.Expr):
                if isinstance(node.value, ast.Call):
                    statements.append({
                        "type": "call",
                        "function": self._ast_to_code(node.value.func),
                        "args": [self._ast_to_code(arg) for arg in node.value.args]
                    })
            elif isinstance(node, ast.Break):
                statements.append({"type": "break"})
            elif isinstance(node, ast.Continue):
                statements.append({"type": "continue"})
        
        return statements

    def _extract_if_chain(self, if_node) -> dict:
        """Extract complete if-elif-else chain with all conditions and bodies."""
        conditions = []
        
        current = if_node
        while current:
            if isinstance(current, ast.If):
                # Extract condition and body
                condition_info = {
                    "test": self._ast_to_code(current.test),
                    "body": self._extract_python_body(current.body)
                }
                conditions.append(condition_info)
                
                # Check if there's an elif or else
                if current.orelse:
                    if len(current.orelse) == 1 and isinstance(current.orelse[0], ast.If):
                        # This is an elif
                        current = current.orelse[0]
                    else:
                        # This is an else
                        conditions.append({
                            "test": "else",
                            "body": self._extract_python_body(current.orelse)
                        })
                        current = None
                else:
                    current = None
            else:
                current = None
        
        return {
            "type": "if_elif_else",
            "conditions": conditions
        }

    # -------------------------------------------------------------------------
    # PYTHON PARSER (Supports both functions and top-level code)
    # -------------------------------------------------------------------------
    def _parse_python(self, filename: str, content: str) -> Dict[str, Any]:
        try:
            tree = ast.parse(content)
        except Exception as e:
            return {"error": f"AST parsing failed: {str(e)}"}

        funcs = []

        # Store reference to self for use in Visitor
        parser_service = self

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
                
                # Extract detailed body information using parser_service reference
                body_details = parser_service._extract_python_body(node.body)
                
                self.funcs.append({
                    "name": node.name,
                    "args": [a.arg for a in node.args.args],
                    "calls": list(set(calls)),
                    "control_flow": list(set(control)),
                    "docstring": ast.get_docstring(node),
                    "body": body_details  # NEW: Detailed body structure
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
    # JavaScript Helper Methods
    # -------------------------------------------------------------------------
    def _extract_js_body(self, body_node) -> list:
        """Extract detailed body information from JavaScript AST nodes."""
        statements = []
        
        if not body_node:
            return statements
        
        # Handle BlockStatement
        body_list = body_node.body if hasattr(body_node, 'body') else [body_node]
        
        for node in body_list:
            if node.type == "IfStatement":
                if_chain = self._extract_js_if_chain(node)
                statements.append(if_chain)
            elif node.type == "ForStatement":
                statements.append({
                    "type": "for_loop",
                    "init": self._js_node_to_code(node.init) if hasattr(node, 'init') and node.init else "",
                    "test": self._js_node_to_code(node.test) if hasattr(node, 'test') and node.test else "",
                    "update": self._js_node_to_code(node.update) if hasattr(node, 'update') and node.update else "",
                    "body": self._extract_js_body(node.body) if hasattr(node, 'body') else []
                })
            elif node.type == "WhileStatement":
                statements.append({
                    "type": "while_loop",
                    "condition": self._js_node_to_code(node.test) if hasattr(node, 'test') else "",
                    "body": self._extract_js_body(node.body) if hasattr(node, 'body') else []
                })
            elif node.type == "ReturnStatement":
                statements.append({
                    "type": "return",
                    "value": self._js_node_to_code(node.argument) if hasattr(node, 'argument') and node.argument else None
                })
            elif node.type == "VariableDeclaration":
                for decl in node.declarations:
                    statements.append({
                        "type": "assignment",
                        "targets": [decl.id.name if hasattr(decl.id, 'name') else str(decl.id)],
                        "value": self._js_node_to_code(decl.init) if hasattr(decl, 'init') and decl.init else ""
                    })
            elif node.type == "ExpressionStatement":
                if hasattr(node, 'expression') and node.expression.type == "CallExpression":
                    statements.append({
                        "type": "call",
                        "function": self._js_node_to_code(node.expression.callee),
                        "args": [self._js_node_to_code(arg) for arg in node.expression.arguments] if hasattr(node.expression, 'arguments') else []
                    })
            elif node.type == "BreakStatement":
                statements.append({"type": "break"})
            elif node.type == "ContinueStatement":
                statements.append({"type": "continue"})
        
        return statements

    def _extract_js_if_chain(self, if_node) -> dict:
        """Extract complete if-elif-else chain from JavaScript."""
        conditions = []
        
        current = if_node
        while current and current.type == "IfStatement":
            condition_info = {
                "test": self._js_node_to_code(current.test) if hasattr(current, 'test') else "",
                "body": self._extract_js_body(current.consequent) if hasattr(current, 'consequent') else []
            }
            conditions.append(condition_info)
            
            # Check for else/else if
            if hasattr(current, 'alternate') and current.alternate:
                if current.alternate.type == "IfStatement":
                    current = current.alternate
                else:
                    # This is an else clause
                    conditions.append({
                        "test": "else",
                        "body": self._extract_js_body(current.alternate)
                    })
                    current = None
            else:
                current = None
        
        return {
            "type": "if_elif_else",
            "conditions": conditions
        }

    def _js_node_to_code(self, node) -> str:
        """Convert JavaScript AST node to code string."""
        if not node:
            return ""
        
        try:
            if node.type == "Identifier":
                return node.name if hasattr(node, 'name') else ""
            elif node.type == "Literal":
                return str(node.value) if hasattr(node, 'value') else ""
            elif node.type == "BinaryExpression":
                left = self._js_node_to_code(node.left) if hasattr(node, 'left') else ""
                right = self._js_node_to_code(node.right) if hasattr(node, 'right') else ""
                op = node.operator if hasattr(node, 'operator') else ""
                return f"{left} {op} {right}"
            elif node.type == "MemberExpression":
                obj = self._js_node_to_code(node.object) if hasattr(node, 'object') else ""
                prop = self._js_node_to_code(node.property) if hasattr(node, 'property') else ""
                return f"{obj}.{prop}"
            elif node.type == "CallExpression":
                callee = self._js_node_to_code(node.callee) if hasattr(node, 'callee') else ""
                return f"{callee}()"
            elif node.type == "UnaryExpression":
                arg = self._js_node_to_code(node.argument) if hasattr(node, 'argument') else ""
                op = node.operator if hasattr(node, 'operator') else ""
                return f"{op}{arg}"
            elif node.type == "LogicalExpression":
                left = self._js_node_to_code(node.left) if hasattr(node, 'left') else ""
                right = self._js_node_to_code(node.right) if hasattr(node, 'right') else ""
                op = node.operator if hasattr(node, 'operator') else ""
                return f"{left} {op} {right}"
            else:
                return node.type
        except:
            return str(node.type) if hasattr(node, 'type') else ""

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

                # Extract detailed body information
                body_details = self._extract_js_body(node.body) if hasattr(node, 'body') else []

                funcs.append({
                    "name": name,
                    "args": args,
                    "calls": list(set(func_calls)),
                    "control_flow": list(set(func_ctrl)),
                    "docstring": None,
                    "body": body_details  # NEW: Detailed body structure
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
    # Java Helper Methods
    # -------------------------------------------------------------------------
    def _extract_java_body(self, node) -> list:
        """Extract detailed body information from Java AST nodes."""
        statements = []
        
        if not node or not hasattr(node, 'body') or not node.body:
            return statements
        
        for child in node.body:
            if isinstance(child, javalang.tree.IfStatement):
                if_chain = self._extract_java_if_chain(child)
                statements.append(if_chain)
            elif isinstance(child, javalang.tree.ForStatement):
                statements.append({
                    "type": "for_loop",
                    "condition": str(child.control) if hasattr(child, 'control') else "",
                    "body": self._extract_java_body(child) if hasattr(child, 'body') else []
                })
            elif isinstance(child, javalang.tree.WhileStatement):
                statements.append({
                    "type": "while_loop",
                    "condition": str(child.condition) if hasattr(child, 'condition') else "",
                    "body": self._extract_java_body(child) if hasattr(child, 'body') else []
                })
            elif isinstance(child, javalang.tree.ReturnStatement):
                statements.append({
                    "type": "return",
                    "value": str(child.expression) if hasattr(child, 'expression') and child.expression else None
                })
            elif isinstance(child, javalang.tree.BreakStatement):
                statements.append({"type": "break"})
            elif isinstance(child, javalang.tree.ContinueStatement):
                statements.append({"type": "continue"})
        
        return statements

    def _extract_java_if_chain(self, if_node) -> dict:
        """Extract if-else chain from Java."""
        conditions = []
        
        current = if_node
        while current and isinstance(current, javalang.tree.IfStatement):
            condition_info = {
                "test": str(current.condition) if hasattr(current, 'condition') else "",
                "body": self._extract_java_body(current) if hasattr(current, 'then_statement') else []
            }
            conditions.append(condition_info)
            
            # Check for else
            if hasattr(current, 'else_statement') and current.else_statement:
                if isinstance(current.else_statement, javalang.tree.IfStatement):
                    current = current.else_statement
                else:
                    conditions.append({
                        "test": "else",
                        "body": self._extract_java_body(current.else_statement) if hasattr(current.else_statement, 'body') else []
                    })
                    current = None
            else:
                current = None
        
        return {
            "type": "if_elif_else",
            "conditions": conditions
        }

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
            
            # Extract detailed body information
            body_details = self._extract_java_body(node) if hasattr(node, 'body') and node.body else []
            
            funcs.append({
                "name": node.name,
                "args": [p.type.name for p in node.parameters if hasattr(p.type, "name")],
                "calls": list(set(calls)),
                "control_flow": list(set(control)),
                "docstring": None,
                "body": body_details  # NEW: Detailed body structure
            })
            all_calls += calls

        return {"language": "java", "functions": funcs, "top_calls": list(set(all_calls))}

    # -------------------------------------------------------------------------
    # C / C++ Helper Methods
    # -------------------------------------------------------------------------
    def _extract_c_cpp_body(self, node, content: str) -> list:
        """Extract basic body information from C/C++ tree-sitter nodes."""
        statements = []
        
        def walk_body(n):
            if n.type == "if_statement":
                # Extract condition from tree-sitter node
                condition_node = None
                for child in n.children:
                    if child.type == "condition":
                        condition_node = child
                        break
                
                condition_text = content[condition_node.start_byte:condition_node.end_byte] if condition_node else ""
                statements.append({
                    "type": "if_elif_else",
                    "conditions": [{"test": condition_text, "body": []}]
                })
            elif n.type in ["for_statement", "while_statement"]:
                condition_text = ""
                for child in n.children:
                    if child.type in ["condition", "for_clause"]:
                        condition_text = content[child.start_byte:child.end_byte]
                        break
                
                loop_type = "for_loop" if n.type == "for_statement" else "while_loop"
                statements.append({
                    "type": loop_type,
                    "condition": condition_text,
                    "body": []
                })
            elif n.type == "return_statement":
                # Extract return value
                return_value = content[n.start_byte:n.end_byte].replace("return", "").strip().rstrip(";").strip()
                statements.append({
                    "type": "return",
                    "value": return_value if return_value else None
                })
            elif n.type == "break_statement":
                statements.append({"type": "break"})
            elif n.type == "continue_statement":
                statements.append({"type": "continue"})
            
            # Recursively walk children
            for child in n.children:
                walk_body(child)
        
        walk_body(node)
        return statements

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
                func_body_node = None
                for c in node.children:
                    if c.type == "identifier":
                        func_name = content[c.start_byte:c.end_byte]
                    elif c.type == "compound_statement":
                        func_body_node = c
                
                # Extract detailed body information
                body_details = self._extract_c_cpp_body(func_body_node, content) if func_body_node else []
                
                funcs.append({
                    "name": func_name or "unnamed_function",
                    "args": [],
                    "calls": [],
                    "control_flow": [],
                    "docstring": None,
                    "body": body_details  # NEW: Detailed body structure
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