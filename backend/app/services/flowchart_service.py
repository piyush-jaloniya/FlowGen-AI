import networkx as nx
from typing import Dict, Any, List
import uuid

class FlowchartService:
    """
    Builds a detailed flowchart in Mermaid syntax from parsed code output.
    Creates a proper flowchart showing sequential operations, decisions, and loops.
    Uses NLP for semantic understanding of code operations.
    """

    def __init__(self, parser=None, nlp=None):
        self.parser = parser
        self.nlp = nlp  # spaCy NLP model
        self.node_counter = 0

    def _sanitize_id(self, text: str) -> str:
        """Sanitize text for use as Mermaid node ID."""
        return text.replace(" ", "_").replace("(", "").replace(")", "").replace("-", "_").replace(".", "_")[:50]

    def _sanitize_label(self, text: str) -> str:
        """Sanitize text for use as Mermaid node label."""
        return text.replace('"', "'").replace("\n", " ")

    def _generate_node_id(self, prefix: str = "Node") -> str:
        """Generate a unique node ID."""
        node_id = f"{prefix}{self.node_counter}"
        self.node_counter += 1
        return node_id

    def _extract_operation_type(self, call_name: str) -> str:
        """
        Use NLP to understand what type of operation a function call represents.
        """
        if not self.nlp or not call_name:
            return "process"
        
        # Common patterns (fast path)
        call_lower = call_name.lower()
        
        # I/O Operations
        if call_lower in ["print", "println", "printf", "cout", "console", "log", "write", "display", "show"]:
            return "output"
        if call_lower in ["input", "scanf", "cin", "read", "readline", "gets", "getline"]:
            return "input"
        
        # Data Operations
        if call_lower in ["append", "push", "add", "insert", "extend"]:
            return "data_add"
        if call_lower in ["pop", "remove", "delete", "clear"]:
            return "data_remove"
        if call_lower in ["sort", "sorted", "reverse"]:
            return "data_sort"
        if call_lower in ["find", "search", "index", "contains"]:
            return "search"
        
        # Mathematical Operations
        if call_lower in ["sum", "total", "count", "max", "min", "avg", "average", "abs", "pow", "sqrt"]:
            return "calculation"
        
        # Use NLP for semantic analysis
        try:
            doc = self.nlp(call_name)
            # Analyze tokens and their types
            for token in doc:
                if token.pos_ == "VERB":
                    lemma = token.lemma_.lower()
                    if lemma in ["print", "display", "show", "output"]:
                        return "output"
                    elif lemma in ["read", "get", "input"]:
                        return "input"
                    elif lemma in ["calculate", "compute", "evaluate"]:
                        return "calculation"
                    elif lemma in ["sort", "order", "arrange"]:
                        return "data_sort"
                    elif lemma in ["search", "find", "locate"]:
                        return "search"
        except:
            pass
        
        return "process"

    def _generate_semantic_label(self, call_name: str, operation_type: str) -> str:
        """
        Generate human-readable label using NLP to convert function names to readable text.
        """
        if not call_name:
            return "Process"
        
        # Convert camelCase or snake_case to readable text
        import re
        # Handle camelCase
        s1 = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', call_name)
        # Handle snake_case
        s2 = s1.replace('_', ' ')
        # Capitalize properly
        readable = ' '.join(word.capitalize() for word in s2.split())
        
        # Add semantic context based on operation type
        if operation_type == "output":
            if not readable.lower().startswith(("print", "display", "output", "show")):
                readable = f"Display {readable}"
        elif operation_type == "input":
            if not readable.lower().startswith(("get", "read", "input")):
                readable = f"Get {readable}"
        elif operation_type == "calculation":
            if not readable.lower().startswith("calculate"):
                readable = f"Calculate {readable}"
        
        return readable

    def _analyze_code_statements(self, func: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Analyze function to extract logical steps using NLP.
        Returns a list of statements with their types and semantic labels.
        """
        statements = []
        
        func_name = func.get("name", "")
        calls = func.get("calls", [])
        control_flows = func.get("control_flow", [])
        
        # Analyze function name semantically
        if func_name != "main" and self.nlp:
            operation_type = self._extract_operation_type(func_name)
            label = self._generate_semantic_label(func_name, operation_type)
            statements.append({"type": "process", "label": label})
        
        # Analyze calls semantically
        seen_operations = set()
        for call in calls:
            op_type = self._extract_operation_type(call)
            
            # Avoid duplicate I/O operations
            if op_type in ["input", "output"] and op_type in seen_operations:
                continue
            seen_operations.add(op_type)
            
            label = self._generate_semantic_label(call, op_type)
            
            if op_type == "output":
                statements.append({"type": "output", "label": label})
            elif op_type == "input":
                statements.append({"type": "input", "label": label})
            elif op_type in ["calculation", "data_sort", "search"]:
                statements.append({"type": "process", "label": label})
        
        # Add control flows
        for ctrl in control_flows:
            statements.append({"type": "decision", "label": f"{ctrl} Condition"})
        
        return statements

    def build(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        if not parsed_data or "functions" not in parsed_data:
            return {"error": "Invalid parsed data for flowchart."}

        self.node_counter = 0
        mermaid_code = "flowchart TD\n"
        
        # Start node
        start_id = "Start"
        mermaid_code += f'    {start_id}([Start])\n'
        prev_node = start_id

        functions = parsed_data.get("functions", [])
        
        # Process each function or main block
        for func_idx, func in enumerate(functions):
            func_name = func.get('name', 'function')
            calls = func.get("calls", [])
            control_flows = func.get("control_flow", [])
            
            # For main block - create detailed step-by-step flow
            if func_name == "main":
                # Analyze the operations in main using NLP
                has_input = any(self._extract_operation_type(c) == "input" for c in calls)
                has_output = any(self._extract_operation_type(c) == "output" for c in calls)
                processing_calls = [c for c in calls if self._extract_operation_type(c) not in ["input", "output"]]
                
                # Initialization/Input step
                if has_input or calls:
                    init_id = self._generate_node_id("Init")
                    if has_input:
                        mermaid_code += f'    {init_id}[/"Get Input"/]\n'
                    else:
                        mermaid_code += f'    {init_id}["Initialization"]\n'
                    mermaid_code += f'    {prev_node} --> {init_id}\n'
                    prev_node = init_id
                
                # Processing step (if there are operations beyond I/O)
                if processing_calls:
                    proc_id = self._generate_node_id("Proc")
                    # Use NLP to generate semantic label
                    if self.nlp and processing_calls:
                        first_call = processing_calls[0]
                        op_type = self._extract_operation_type(first_call)
                        label = self._generate_semantic_label(first_call, op_type)
                        mermaid_code += f'    {proc_id}["{label}"]\n'
                    else:
                        mermaid_code += f'    {proc_id}["Processing Data"]\n'
                    mermaid_code += f'    {prev_node} --> {proc_id}\n'
                    prev_node = proc_id
                
                # Control flow structures
                for ctrl in control_flows:
                    ctrl_id = self._generate_node_id("Ctrl")
                    mermaid_code += f'    {ctrl_id}{{{{{ctrl} Condition}}}}\n'
                    mermaid_code += f'    {prev_node} --> {ctrl_id}\n'
                    
                    # Add True/False branches for decisions
                    if ctrl == "If":
                        true_id = self._generate_node_id("True")
                        false_id = self._generate_node_id("False")
                        mermaid_code += f'    {true_id}["True Branch"]\n'
                        mermaid_code += f'    {false_id}["False Branch"]\n'
                        mermaid_code += f'    {ctrl_id} -->|Yes| {true_id}\n'
                        mermaid_code += f'    {ctrl_id} -->|No| {false_id}\n'
                        
                        # Merge back
                        merge_id = self._generate_node_id("Merge")
                        mermaid_code += f'    {merge_id}["Continue"]\n'
                        mermaid_code += f'    {true_id} --> {merge_id}\n'
                        mermaid_code += f'    {false_id} --> {merge_id}\n'
                        prev_node = merge_id
                    elif ctrl in ["For", "While"]:
                        loop_body = self._generate_node_id("Loop")
                        mermaid_code += f'    {loop_body}["Loop Body"]\n'
                        mermaid_code += f'    {ctrl_id} -->|Continue| {loop_body}\n'
                        mermaid_code += f'    {loop_body} --> {ctrl_id}\n'
                        
                        exit_id = self._generate_node_id("Exit")
                        mermaid_code += f'    {exit_id}["Exit Loop"]\n'
                        mermaid_code += f'    {ctrl_id} -->|Done| {exit_id}\n'
                        prev_node = exit_id
                    else:
                        prev_node = ctrl_id
                
                # Output step
                if has_output:
                    out_id = self._generate_node_id("Out")
                    mermaid_code += f'    {out_id}[/"Output Result"/]\n'
                    mermaid_code += f'    {prev_node} --> {out_id}\n'
                    prev_node = out_id
                        
            else:
                # For defined functions - use NLP to understand and label
                func_id = self._generate_node_id("Func")
                label = self._generate_semantic_label(func_name, "process")
                mermaid_code += f'    {func_id}["{label}"]\n'
                mermaid_code += f'    {prev_node} --> {func_id}\n'
                prev_node = func_id
                
                # Show function internals using NLP analysis
                statements = self._analyze_code_statements(func)
                for stmt in statements:
                    stmt_id = self._generate_node_id("Stmt")
                    label = self._sanitize_label(stmt["label"])
                    
                    if stmt["type"] == "decision":
                        mermaid_code += f'    {stmt_id}{{{{{label}}}}}\n'
                    elif stmt["type"] == "output" or stmt["type"] == "input":
                        mermaid_code += f'    {stmt_id}[/"{label}"/]\n'
                    else:
                        mermaid_code += f'    {stmt_id}["{label}"]\n'
                    
                    mermaid_code += f'    {prev_node} --> {stmt_id}\n'
                    prev_node = stmt_id

        # End node
        end_id = "End"
        mermaid_code += f'    {end_id}([End])\n'
        mermaid_code += f'    {prev_node} --> {end_id}\n'

        return {
            "language": parsed_data.get("language", "unknown"),
            "mermaid": mermaid_code
        }
        if not parsed_data or "functions" not in parsed_data:
            return {"error": "Invalid parsed data for flowchart."}

        self.node_counter = 0
        mermaid_code = "flowchart TD\n"
        
        # Start node
        start_id = "Start"
        mermaid_code += f'    {start_id}([Start])\n'
        prev_node = start_id

        functions = parsed_data.get("functions", [])
        
        # Process each function or main block
        for func_idx, func in enumerate(functions):
            func_name = func.get('name', 'function')
            calls = func.get("calls", [])
            control_flows = func.get("control_flow", [])
            
            # For main block - create detailed step-by-step flow
            if func_name == "main":
                # Analyze the operations in main
                statements = []
                
                # Detect initialization (assignments, variable declarations)
                if calls:
                    # Check for common patterns
                    has_input = any(c in ["input", "eval", "int"] for c in calls)
                    has_output = any(c in ["print"] for c in calls)
                    
                    # Initialization step
                    init_id = self._generate_node_id("Init")
                    mermaid_code += f'    {init_id}["Initialization"]\n'
                    mermaid_code += f'    {prev_node} --> {init_id}\n'
                    prev_node = init_id
                    
                    # Processing/operations step
                    if len(calls) > 1:
                        proc_id = self._generate_node_id("Proc")
                        # Determine operation type from code context
                        mermaid_code += f'    {proc_id}["Processing Data"]\n'
                        mermaid_code += f'    {prev_node} --> {proc_id}\n'
                        prev_node = proc_id
                    
                    # Output step
                    if has_output:
                        out_id = self._generate_node_id("Out")
                        mermaid_code += f'    {out_id}["Output Result"]\n'
                        mermaid_code += f'    {prev_node} --> {out_id}\n'
                        prev_node = out_id
                
                # Add control flow structures
                for ctrl in control_flows:
                    ctrl_id = self._generate_node_id("Ctrl")
                    mermaid_code += f'    {ctrl_id}{{{{{ctrl} Condition}}}}\n'
                    mermaid_code += f'    {prev_node} --> {ctrl_id}\n'
                    
                    # Add True/False branches for decisions
                    if ctrl in ["If"]:
                        true_id = self._generate_node_id("True")
                        false_id = self._generate_node_id("False")
                        mermaid_code += f'    {true_id}["True Branch"]\n'
                        mermaid_code += f'    {false_id}["False Branch"]\n'
                        mermaid_code += f'    {ctrl_id} -->|Yes| {true_id}\n'
                        mermaid_code += f'    {ctrl_id} -->|No| {false_id}\n'
                        
                        # Merge back
                        merge_id = self._generate_node_id("Merge")
                        mermaid_code += f'    {merge_id}["Continue"]\n'
                        mermaid_code += f'    {true_id} --> {merge_id}\n'
                        mermaid_code += f'    {false_id} --> {merge_id}\n'
                        prev_node = merge_id
                    else:
                        prev_node = ctrl_id
                        
            else:
                # For defined functions - show as process box
                func_id = self._generate_node_id("Func")
                label = self._sanitize_label(f"{func_name}()")
                mermaid_code += f'    {func_id}["{label}"]\n'
                mermaid_code += f'    {prev_node} --> {func_id}\n'
                prev_node = func_id
                
                # Show function internals
                statements = self._analyze_code_statements(func)
                for stmt in statements:
                    stmt_id = self._generate_node_id("Stmt")
                    label = self._sanitize_label(stmt["label"])
                    
                    if stmt["type"] == "decision":
                        mermaid_code += f'    {stmt_id}{{{{{label}}}}}\n'
                    elif stmt["type"] == "output" or stmt["type"] == "input":
                        mermaid_code += f'    {stmt_id}[/"{label}"/]\n'
                    else:
                        mermaid_code += f'    {stmt_id}["{label}"]\n'
                    
                    mermaid_code += f'    {prev_node} --> {stmt_id}\n'
                    prev_node = stmt_id

        # End node
        end_id = "End"
        mermaid_code += f'    {end_id}([End])\n'
        mermaid_code += f'    {prev_node} --> {end_id}\n'

        return {
            "language": parsed_data.get("language", "unknown"),
            "mermaid": mermaid_code
        }
