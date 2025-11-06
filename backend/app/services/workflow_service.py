from typing import Dict, Any
import uuid
import re

class WorkflowService:
    """
    Generates a high-level workflow in Mermaid syntax
    showing the logical steps and operations in the code.
    Uses NLP for semantic understanding and better labeling.
    """

    def __init__(self, parser=None, nlp=None):
        self.parser = parser
        self.nlp = nlp  # spaCy NLP model
        
    def _sanitize_label(self, text: str) -> str:
        """Sanitize text for use as Mermaid node label."""
        return text.replace('"', "'").replace("\n", " ")

    def _humanize_text(self, text: str) -> str:
        """
        Convert camelCase or snake_case to human-readable text using NLP if available.
        """
        if not text:
            return ""
        
        # Handle camelCase
        s1 = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', text)
        # Handle snake_case
        s2 = s1.replace('_', ' ')
        # Capitalize properly
        readable = ' '.join(word.capitalize() for word in s2.split())
        
        # Use NLP for better understanding if available
        if self.nlp:
            try:
                doc = self.nlp(readable)
                # Extract key verbs and nouns for better semantic understanding
                verbs = [token.lemma_.capitalize() for token in doc if token.pos_ == "VERB"]
                nouns = [token.text.capitalize() for token in doc if token.pos_ == "NOUN"]
                
                if verbs and nouns:
                    return f"{verbs[0]} {' '.join(nouns)}"
                elif verbs:
                    return verbs[0]
            except:
                pass
        
        return readable

    def _extract_operation_semantics(self, call_name: str) -> tuple:
        """
        Use NLP to understand what type of operation a function represents.
        Returns (operation_type, human_label)
        """
        if not call_name:
            return ("process", "Process")
        
        call_lower = call_name.lower()
        
        # Direct mappings for common operations
        operation_map = {
            "print": ("output", "Display Output"),
            "println": ("output", "Display Output"),
            "printf": ("output", "Display Output"),
            "console": ("output", "Display Output"),
            "log": ("output", "Display Output"),
            "input": ("input", "Get Input"),
            "scanf": ("input", "Get Input"),
            "readline": ("input", "Get Input"),
            "read": ("input", "Get Input"),
            "sort": ("sort", "Sort Data"),
            "sorted": ("sort", "Sort Data"),
            "reverse": ("sort", "Reverse Data"),
            "append": ("data_mod", "Add Data"),
            "push": ("data_mod", "Add Data"),
            "pop": ("data_mod", "Remove Data"),
            "remove": ("data_mod", "Remove Data"),
            "find": ("search", "Search Data"),
            "search": ("search", "Search Data"),
            "sum": ("calc", "Calculate Sum"),
            "max": ("calc", "Find Maximum"),
            "min": ("calc", "Find Minimum"),
        }
        
        if call_lower in operation_map:
            return operation_map[call_lower]
        
        # Use NLP for semantic analysis
        if self.nlp:
            try:
                doc = self.nlp(call_name)
                for token in doc:
                    if token.pos_ == "VERB":
                        lemma = token.lemma_.lower()
                        if lemma in ["print", "display", "show", "output", "write"]:
                            return ("output", self._humanize_text(call_name))
                        elif lemma in ["read", "get", "input", "scan"]:
                            return ("input", self._humanize_text(call_name))
                        elif lemma in ["sort", "order", "arrange"]:
                            return ("sort", self._humanize_text(call_name))
                        elif lemma in ["calculate", "compute", "evaluate"]:
                            return ("calc", self._humanize_text(call_name))
                        elif lemma in ["search", "find", "locate"]:
                            return ("search", self._humanize_text(call_name))
                        elif lemma in ["swap", "exchange", "switch"]:
                            return ("swap", "Swap Elements")
            except:
                pass
        
        # Fallback: humanize the name
        return ("process", self._humanize_text(call_name))

    def _infer_step_type(self, func_name: str, calls: list) -> str:
        """Infer the type of step based on function name and calls using NLP."""
        name_lower = func_name.lower()
        
        # Check function name patterns
        if name_lower == "main":
            return "main"
        
        # Use NLP to analyze function name
        if self.nlp:
            try:
                doc = self.nlp(func_name)
                for token in doc:
                    lemma = token.lemma_.lower()
                    if lemma in ["initialize", "init", "setup", "start"]:
                        return "initialization"
                    elif lemma in ["swap", "exchange", "switch"]:
                        return "swapping"
                    elif lemma in ["sort", "order", "arrange"]:
                        return "sorting"
                    elif lemma in ["search", "find", "locate"]:
                        return "searching"
                    elif lemma in ["print", "display", "show", "output"]:
                        return "output"
                    elif lemma in ["input", "read", "get"]:
                        return "input"
                    elif lemma in ["calculate", "compute", "evaluate"]:
                        return "calculation"
                    elif lemma in ["process", "handle", "execute"]:
                        return "processing"
            except:
                pass
        
        # Keyword matching fallback
        keyword_map = {
            "init": "initialization",
            "setup": "initialization",
            "swap": "swapping",
            "sort": "sorting",
            "search": "searching",
            "find": "searching",
            "print": "output",
            "display": "output",
            "output": "output",
            "input": "input",
            "read": "input",
            "calculate": "calculation",
            "compute": "calculation",
            "process": "processing",
        }
        
        for keyword, step_type in keyword_map.items():
            if keyword in name_lower:
                return step_type
        
        # Check calls
        if calls:
            for call in calls:
                op_type, _ = self._extract_operation_semantics(call)
                if op_type == "output":
                    return "output"
                elif op_type == "input":
                    return "input"
        
        return "process"

    def build(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        if not parsed_data or "functions" not in parsed_data:
            return {"error": "Invalid parsed data for workflow."}

        mermaid_code = "flowchart TD\n"
        
        prev_id = None
        node_counter = 0
        
        # Start node
        start_id = "Start"
        mermaid_code += f'    {start_id}([Start])\n'
        prev_id = start_id

        functions = parsed_data["functions"]
        
        for func in functions:
            func_name = func.get("name", "unknown")
            calls = func.get("calls", [])
            step_type = self._infer_step_type(func_name, calls)
            
            # For main block, break it down into logical steps using NLP
            if func_name == "main":
                # Analyze calls to determine workflow steps
                input_calls = []
                output_calls = []
                process_calls = []
                
                for call in calls:
                    op_type, label = self._extract_operation_semantics(call)
                    if op_type == "input":
                        input_calls.append((call, label))
                    elif op_type == "output":
                        output_calls.append((call, label))
                    else:
                        process_calls.append((call, label, op_type))
                
                # Input step
                if input_calls:
                    node_id = f"Step{node_counter}"
                    node_counter += 1
                    label = input_calls[0][1] if len(input_calls) == 1 else "Get Input"
                    mermaid_code += f'    {node_id}["{label}"]\n'
                    mermaid_code += f'    {prev_id} --> {node_id}\n'
                    prev_id = node_id
                elif calls:  # Initialization if no explicit input
                    node_id = f"Step{node_counter}"
                    node_counter += 1
                    mermaid_code += f'    {node_id}["Initialization"]\n'
                    mermaid_code += f'    {prev_id} --> {node_id}\n'
                    prev_id = node_id
                
                # Processing steps - use NLP to create meaningful labels
                for call, label, op_type in process_calls:
                    node_id = f"Step{node_counter}"
                    node_counter += 1
                    
                    # Create semantic label based on operation type
                    if op_type == "swap":
                        final_label = "Swapping Elements"
                    elif op_type == "sort":
                        final_label = "Sorting Data"
                    elif op_type == "search":
                        final_label = "Searching Data"
                    elif op_type == "calc":
                        final_label = label
                    else:
                        final_label = label
                    
                    mermaid_code += f'    {node_id}["{final_label}"]\n'
                    mermaid_code += f'    {prev_id} --> {node_id}\n'
                    prev_id = node_id
                
                # Output step
                if output_calls:
                    node_id = f"Step{node_counter}"
                    node_counter += 1
                    label = output_calls[0][1] if len(output_calls) == 1 else "Display Output"
                    mermaid_code += f'    {node_id}["{label}"]\n'
                    mermaid_code += f'    {prev_id} --> {node_id}\n'
                    prev_id = node_id
            else:
                # Regular function - use NLP for semantic labeling
                node_id = f"Step{node_counter}"
                node_counter += 1
                
                # Generate semantic label
                if step_type == "swapping":
                    label = "Swapping Elements"
                elif step_type == "sorting":
                    label = "Sorting Data"
                elif step_type == "output":
                    label = "Display Output"
                elif step_type == "input":
                    label = "Get Input"
                elif step_type == "initialization":
                    label = "Initialization"
                elif step_type == "searching":
                    label = "Searching Data"
                elif step_type == "calculation":
                    label = self._humanize_text(func_name)
                else:
                    label = self._humanize_text(func_name)
                
                mermaid_code += f'    {node_id}["{self._sanitize_label(label)}"]\n'
                mermaid_code += f'    {prev_id} --> {node_id}\n'
                prev_id = node_id
        
        # End node
        end_id = "End"
        mermaid_code += f'    {end_id}([End])\n'
        mermaid_code += f'    {prev_id} --> {end_id}\n'

        return {
            "language": parsed_data.get("language", "unknown"),
            "mermaid": mermaid_code
        }
        if not parsed_data or "functions" not in parsed_data:
            return {"error": "Invalid parsed data for workflow."}

        mermaid_code = "flowchart LR\n"
        
        prev_id = None
        node_counter = 0
        
        # Start node
        start_id = "Start"
        mermaid_code += f'    {start_id}([Start])\n'
        prev_id = start_id

        functions = parsed_data["functions"]
        
        for func in functions:
            func_name = func.get("name", "unknown")
            calls = func.get("calls", [])
            step_type = self._infer_step_type(func_name, calls)
            
            # For main block, break it down into logical steps
            if func_name == "main":
                # Create steps based on operations detected
                has_print = any(c == "print" for c in calls)
                
                # Initialization step
                if calls:
                    node_id = f"Step{node_counter}"
                    node_counter += 1
                    mermaid_code += f'    {node_id}["Initialization"]\n'
                    mermaid_code += f'    {prev_id} --> {node_id}\n'
                    prev_id = node_id
                    
                    # If there are multiple operations, add processing step
                    if len(calls) > 1:
                        node_id = f"Step{node_counter}"
                        node_counter += 1
                        mermaid_code += f'    {node_id}["Swapping Elements"]\n'
                        mermaid_code += f'    {prev_id} --> {node_id}\n'
                        prev_id = node_id
                    
                    # Output step
                    if has_print:
                        node_id = f"Step{node_counter}"
                        node_counter += 1
                        mermaid_code += f'    {node_id}["Output List"]\n'
                        mermaid_code += f'    {prev_id} --> {node_id}\n'
                        prev_id = node_id
            else:
                # Regular function
                node_id = f"Step{node_counter}"
                node_counter += 1
                
                # Determine label based on step type
                if step_type == "swapping":
                    label = "Swapping Elements"
                elif step_type == "sorting":
                    label = "Sorting Data"
                elif step_type == "output":
                    label = "Output Result"
                elif step_type == "input":
                    label = "Get Input"
                elif step_type == "initialization":
                    label = "Initialization"
                else:
                    label = self._sanitize_label(func_name)
                
                mermaid_code += f'    {node_id}["{label}"]\n'
                mermaid_code += f'    {prev_id} --> {node_id}\n'
                prev_id = node_id
        
        # End node
        end_id = "End"
        mermaid_code += f'    {end_id}([End])\n'
        mermaid_code += f'    {prev_id} --> {end_id}\n'

        return {
            "language": parsed_data.get("language", "unknown"),
            "mermaid": mermaid_code
        }
