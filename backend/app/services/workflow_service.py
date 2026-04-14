from typing import Dict, Any
import re
from .cache_service import cached_diagram
from .identifier_formatter import IdentifierFormatter

class WorkflowService:
    """
    Generates a high-level workflow in Mermaid syntax
    showing the logical steps and operations in the code.
    Uses NLP for semantic understanding and better labeling.
    """

    def __init__(self, parser=None, nlp=None):
        self.parser = parser
        self.nlp = nlp  # spaCy NLP model
        self.formatter = IdentifierFormatter(nlp=nlp)
        
    def _sanitize_label(self, text: str) -> str:
        """Sanitize text for use as Mermaid node label."""
        if not text:
            return ""
        # Replace problematic characters for Mermaid
        text = text.replace('"', "'")
        text = text.replace('\n', ' ')
        text = text.replace('\r', '')
        text = text.replace('[', '(')
        text = text.replace(']', ')')
        text = text.replace('{', '(')
        text = text.replace('}', ')')
        text = text.replace('#', 'num')
        text = text.replace('&', 'and')
        text = text.replace('<', 'lt')
        text = text.replace('>', 'gt')
        # Remove any remaining special chars that might break Mermaid
        text = ''.join(c if c.isprintable() and c not in '|;' else ' ' for c in text)
        # Collapse multiple spaces
        text = ' '.join(text.split())
        return text[:100]  # Limit length

    def _get_mermaid_styles(self) -> str:
        """Return Mermaid CSS class definitions for node styling (Traditional Flowchart Colors)."""
        return """    classDef decisionStyle fill:#FFF4CC,stroke:#E6B800,color:#000,stroke-width:2px
    classDef processStyle fill:#CCE5FF,stroke:#3399FF,color:#000,stroke-width:2px
    classDef loopStyle fill:#FFE5CC,stroke:#FF9933,color:#000,stroke-width:2px
    classDef controlStyle fill:#FFCCCC,stroke:#CC0000,color:#000,stroke-width:2px
    classDef returnStyle fill:#E6CCFF,stroke:#9933FF,color:#000,stroke-width:2px
    classDef inputStyle fill:#CCFFCC,stroke:#33CC33,color:#000,stroke-width:2px
    classDef startEndStyle fill:#FFCCCC,stroke:#FF6666,color:#000,stroke-width:3px
    classDef functionStyle fill:#E6F2FF,stroke:#6699CC,color:#000,stroke-width:2px
    classDef summaryStyle fill:#FFFFCC,stroke:#CCCC00,color:#000,stroke-width:2px"""

    def _humanize_text(self, text: str) -> str:
        """Use formatter to convert identifiers to human-readable text."""
        return self.formatter.humanize_identifier(text)

    def _extract_operation_type(self, call_name: str) -> tuple:
        """Use formatter to detect operation type and humanize the name."""
        op_type = self.formatter.detect_operation_type(call_name)
        humanized = self.formatter.humanize_identifier(call_name, op_type)
        return (op_type, humanized)

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
                op_type, _ = self._extract_operation_type(call)
                if op_type == "output":
                    return "output"
                elif op_type == "input":
                    return "input"
        
        return "process"

    def _build_workflow_from_body(self, body: list, node_counter: int, mermaid_lines: list, prev_id: str) -> tuple:
        """
        Build workflow from detailed body structure (simplified, high-level view).
        Returns (last_node_id, updated_node_counter).
        """
        current_id = prev_id
        
        for stmt in body:
            stmt_type = stmt.get("type", "")
            
            if stmt_type == "if_elif_else":
                # Simplified: just show "Decision Logic"
                node_id = f"Step{node_counter}"
                node_counter += 1
                conditions = stmt.get("conditions", [])
                
                # Create a summary of the decision
                if len(conditions) > 1:
                    mermaid_lines.append(f'    {node_id}["Evaluate Conditions"]:::decisionStyle')
                else:
                    test = conditions[0].get("test", "") if conditions else ""
                    label = f"Check: {self._sanitize_label(test)}" if test != "else" else "Process"
                    mermaid_lines.append(f'    {node_id}["{label}"]:::decisionStyle')
                
                mermaid_lines.append(f'    {current_id} --> {node_id}')
                current_id = node_id
                
            elif stmt_type == "for_loop":
                node_id = f"Step{node_counter}"
                node_counter += 1
                condition = stmt.get("condition", stmt.get("iter", ""))
                label = f"Loop: {self._sanitize_label(str(condition))}" if condition else "Process Loop"
                mermaid_lines.append(f'    {node_id}["{label}"]:::loopStyle')
                mermaid_lines.append(f'    {current_id} --> {node_id}')
                current_id = node_id
                
            elif stmt_type == "while_loop":
                node_id = f"Step{node_counter}"
                node_counter += 1
                condition = stmt.get("condition", "")
                label = f"While: {self._sanitize_label(str(condition))}" if condition else "Process Loop"
                mermaid_lines.append(f'    {node_id}["{label}"]:::loopStyle')
                mermaid_lines.append(f'    {current_id} --> {node_id}')
                current_id = node_id
                
            elif stmt_type == "return":
                node_id = f"Step{node_counter}"
                node_counter += 1
                value = stmt.get("value", "")
                label = f"Return {self._sanitize_label(str(value))}" if value else "Return Result"
                mermaid_lines.append(f'    {node_id}["{label}"]:::returnStyle')
                mermaid_lines.append(f'    {current_id} --> {node_id}')
                current_id = node_id
                
            elif stmt_type == "assignment":
                # Group assignments together in workflow (simplified)
                targets = stmt.get("targets", [])
                if targets:
                    node_id = f"Step{node_counter}"
                    node_counter += 1
                    target_str = ", ".join(str(t) for t in targets)
                    label = f"Set {self._sanitize_label(target_str)}"
                    mermaid_lines.append(f'    {node_id}["{label}"]:::processStyle')
                    mermaid_lines.append(f'    {current_id} --> {node_id}')
                    current_id = node_id
                    
            elif stmt_type == "call":
                node_id = f"Step{node_counter}"
                node_counter += 1
                function = stmt.get("function", "")
                label = f"Call {self._humanize_text(str(function))}" if function else "Process"
                mermaid_lines.append(f'    {node_id}["{label}"]:::processStyle')
                mermaid_lines.append(f'    {current_id} --> {node_id}')
                current_id = node_id
        
        return (current_id, node_counter)


    @cached_diagram('workflow')
    def build(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        if not parsed_data or "functions" not in parsed_data:
            return {"error": "Invalid parsed data for workflow."}

        mermaid_lines = []
        mermaid_lines.append("flowchart TD")
        
        prev_id = None
        node_counter = 0
        
        # Start node
        start_id = "Start"
        mermaid_lines.append(f'    {start_id}([Start]):::startEndStyle')
        prev_id = start_id

        functions = parsed_data["functions"]
        metadata = parsed_data.get("metadata", {})
        
        # Add project summary if available (from smart merging)
        if metadata:
            total_funcs = metadata.get('total_functions', 0)
            selected = metadata.get('selected_functions', 0)
            filtered = metadata.get('filtered_out', 0)
            
            if filtered > 0:
                summary_node = "Summary"
                summary_text = f"Showing {selected}/{total_funcs} functions (filtered {filtered} trivial)"
                mermaid_lines.append(f'    {summary_node}["{summary_text}"]:::summaryStyle')
                mermaid_lines.append(f'    {prev_id} --> {summary_node}')
                prev_id = summary_node
                node_counter += 1
        
        for func in functions:
            func_name = func.get("name", "unknown")
            body = func.get("body", [])
            calls = func.get("calls", [])
            
            # If function has detailed body, use it
            if body:
                # Add function entry node (except for main)
                if func_name != "main":
                    node_id = f"Step{node_counter}"
                    node_counter += 1
                    label = self._humanize_text(func_name)
                    mermaid_lines.append(f'    {node_id}["{self._sanitize_label(label)}"]:::functionStyle')
                    mermaid_lines.append(f'    {prev_id} --> {node_id}')
                    prev_id = node_id
                
                # Build workflow from detailed body
                prev_id, node_counter = self._build_workflow_from_body(body, node_counter, mermaid_lines, prev_id)
                
            else:
                # Fallback to old method if no detailed body available
                step_type = self._infer_step_type(func_name, calls)
                
                # For main block, break it down into logical steps using NLP
                if func_name == "main":
                    # Analyze calls to determine workflow steps
                    input_calls = []
                    output_calls = []
                    process_calls = []
                    
                    for call in calls:
                        op_type, label = self._extract_operation_type(call)
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
                        mermaid_lines.append(f'    {node_id}["{label}"]:::inputStyle')
                        mermaid_lines.append(f'    {prev_id} --> {node_id}')
                        prev_id = node_id
                    elif calls:  # Initialization if no explicit input
                        node_id = f"Step{node_counter}"
                        node_counter += 1
                        mermaid_lines.append(f'    {node_id}["Initialization"]:::processStyle')
                        mermaid_lines.append(f'    {prev_id} --> {node_id}')
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
                        
                        mermaid_lines.append(f'    {node_id}["{final_label}"]:::processStyle')
                        mermaid_lines.append(f'    {prev_id} --> {node_id}')
                        prev_id = node_id
                    
                    # Output step
                    if output_calls:
                        node_id = f"Step{node_counter}"
                        node_counter += 1
                        label = output_calls[0][1] if len(output_calls) == 1 else "Display Output"
                        mermaid_lines.append(f'    {node_id}["{label}"]:::inputStyle')
                        mermaid_lines.append(f'    {prev_id} --> {node_id}')
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
                    
                    mermaid_lines.append(f'    {node_id}["{self._sanitize_label(label)}"]:::functionStyle')
                    mermaid_lines.append(f'    {prev_id} --> {node_id}')
                    prev_id = node_id
        
        # End node
        end_id = "End"
        mermaid_lines.append(f'    {end_id}([End]):::startEndStyle')
        mermaid_lines.append(f'    {prev_id} --> {end_id}')

        # Add Mermaid CSS styles
        mermaid_lines.append("")
        mermaid_lines.append(self._get_mermaid_styles())

        mermaid_code = "\n".join(mermaid_lines) + "\n"
        
        # Debug logging
        logger.info(f"Generated workflow with {len(mermaid_lines)} lines")
        logger.debug(f"First 500 chars of mermaid: {mermaid_code[:500]}")

        return {
            "language": parsed_data.get("language", "unknown"),
            "mermaid": mermaid_code
        }
