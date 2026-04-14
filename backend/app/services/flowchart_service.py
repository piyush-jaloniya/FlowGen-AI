from typing import Dict, Any, List
from .cache_service import cached_diagram
from .identifier_formatter import IdentifierFormatter

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
        self.formatter = IdentifierFormatter(nlp=nlp)

    def _sanitize_id(self, text: str) -> str:
        """Sanitize text for use as Mermaid node ID."""
        return text.replace(" ", "_").replace("(", "").replace(")", "").replace("-", "_").replace(".", "_")[:50]

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

    def _generate_node_id(self, prefix: str = "Node") -> str:
        """Generate a unique node ID."""
        node_id = f"{prefix}{self.node_counter}"
        self.node_counter += 1
        return node_id

    def _get_mermaid_styles(self) -> str:
        """Return Mermaid CSS class definitions for node styling (Traditional Flowchart Colors)."""
        return """    classDef decisionStyle fill:#FFF4CC,stroke:#E6B800,color:#000,stroke-width:2px
    classDef processStyle fill:#CCE5FF,stroke:#3399FF,color:#000,stroke-width:2px
    classDef loopStyle fill:#FFE5CC,stroke:#FF9933,color:#000,stroke-width:2px
    classDef controlStyle fill:#FFCCCC,stroke:#CC0000,color:#000,stroke-width:2px
    classDef returnStyle fill:#E6CCFF,stroke:#9933FF,color:#000,stroke-width:2px
    classDef inputStyle fill:#CCFFCC,stroke:#33CC33,color:#000,stroke-width:2px
    classDef outputStyle fill:#FFCCFF,stroke:#FF66FF,color:#000,stroke-width:2px
    classDef startEndStyle fill:#FFCCCC,stroke:#FF6666,color:#000,stroke-width:3px
    classDef functionStyle fill:#E6F2FF,stroke:#6699CC,color:#000,stroke-width:2px
    classDef summaryStyle fill:#FFFFCC,stroke:#CCCC00,color:#000,stroke-width:2px"""



    def _format_condition_label(self, condition: str, max_length: int = 50) -> str:
        """Format condition for display in flowchart."""
        if not condition:
            return "condition"
        
        # Clean up the condition
        condition = condition.strip()
        
        # Truncate if too long
        if len(condition) > max_length:
            condition = condition[:max_length-3] + "..."
        
        return condition

    def _format_return_label(self, value: str) -> str:
        """Format return statement label with icon."""
        if value:
            return f"Return {self._sanitize_label(str(value))}"
        return "Return"

    def _extract_operation_type(self, call_name: str) -> str:
        """Use formatter to detect operation type."""
        return self.formatter.detect_operation_type(call_name)

    def _generate_semantic_label(self, call_name: str, operation_type: str) -> str:
        """Use formatter to generate human-readable label."""
        return self.formatter.humanize_identifier(call_name, operation_type)

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

    def _build_flowchart_from_body(self, body: list, prev_node: str, mermaid_lines: list) -> str:
        """
        Build flowchart from detailed body structure.
        Returns the ID of the last node created.
        """
        current_node = prev_node
        
        for stmt in body:
            stmt_type = stmt.get("type", "")
            
            if stmt_type == "if_elif_else":
                # Handle if-elif-else chain
                conditions = stmt.get("conditions", [])
                merge_node = self._generate_node_id("Merge")
                
                for idx, cond in enumerate(conditions):
                    test = cond.get("test", "")
                    body_stmts = cond.get("body", [])
                    
                    if test == "else":
                        # Else branch
                        else_node = self._generate_node_id("Else")
                        mermaid_lines.append(f'    {else_node}["Else Branch"]:::processStyle')
                        mermaid_lines.append(f'    {current_node} -->|No| {else_node}')
                        
                        # Process else body
                        last_else = self._build_flowchart_from_body(body_stmts, else_node, mermaid_lines)
                        mermaid_lines.append(f'    {last_else} --> {merge_node}')
                    else:
                        # If or elif condition
                        cond_node = self._generate_node_id("Cond")
                        formatted_test = self._format_condition_label(test)
                        mermaid_lines.append(f'    {cond_node}{{{{{self._sanitize_label(formatted_test)}?}}}}:::decisionStyle')
                        
                        if idx == 0:
                            # First condition connects from previous node
                            mermaid_lines.append(f'    {current_node} --> {cond_node}')
                        else:
                            # Subsequent conditions connect from previous condition's No branch
                            mermaid_lines.append(f'    {current_node} -->|No| {cond_node}')
                        
                        # Process condition body
                        if body_stmts:
                            # Check if body contains a return statement
                            has_return = any(s.get("type") == "return" for s in body_stmts)
                            
                            if has_return:
                                # Build the body and connect to End directly
                                last_body = self._build_flowchart_from_body(body_stmts, cond_node, mermaid_lines)
                                # Don't connect to merge, return goes to End
                            else:
                                # Build the body and connect to merge
                                last_body = self._build_flowchart_from_body(body_stmts, cond_node, mermaid_lines)
                                mermaid_lines.append(f'    {last_body} --> {merge_node}')
                        else:
                            # Empty body, connect Yes branch to merge
                            yes_node = self._generate_node_id("Yes")
                            mermaid_lines.append(f'    {yes_node}["True Branch"]:::processStyle')
                            mermaid_lines.append(f'    {cond_node} -->|Yes| {yes_node}')
                            mermaid_lines.append(f'    {yes_node} --> {merge_node}')
                        
                        current_node = cond_node
                
                # If no else clause, connect last condition's No to merge
                if not any(c.get("test") == "else" for c in conditions):
                    mermaid_lines.append(f'    {current_node} -->|No| {merge_node}')
                
                mermaid_lines.append(f'    {merge_node}["Continue"]:::processStyle')
                current_node = merge_node
                
            elif stmt_type == "for_loop":
                # Handle for loop
                loop_node = self._generate_node_id("Loop")
                loop_body_node = self._generate_node_id("LoopBody")
                exit_node = self._generate_node_id("Exit")
                
                condition = stmt.get("condition", stmt.get("iter", ""))
                formatted_cond = self._format_condition_label(f"For {condition}")
                mermaid_lines.append(f'    {loop_node}{{{{{self._sanitize_label(formatted_cond)}?}}}}:::loopStyle')
                mermaid_lines.append(f'    {current_node} --> {loop_node}')
                
                # Loop body
                body_stmts = stmt.get("body", [])
                if body_stmts:
                    last_body = self._build_flowchart_from_body(body_stmts, loop_node, mermaid_lines)
                    mermaid_lines.append(f'    {last_body} --> {loop_node}')
                else:
                    mermaid_lines.append(f'    {loop_body_node}["Loop Body"]:::processStyle')
                    mermaid_lines.append(f'    {loop_node} -->|Continue| {loop_body_node}')
                    mermaid_lines.append(f'    {loop_body_node} --> {loop_node}')
                
                mermaid_lines.append(f'    {exit_node}["Exit Loop"]:::processStyle')
                mermaid_lines.append(f'    {loop_node} -->|Done| {exit_node}')
                current_node = exit_node
                
            elif stmt_type == "while_loop":
                # Handle while loop
                loop_node = self._generate_node_id("While")
                loop_body_node = self._generate_node_id("WhileBody")
                exit_node = self._generate_node_id("WhileExit")
                
                condition = stmt.get("condition", "")
                formatted_cond = self._format_condition_label(f"While {condition}")
                mermaid_lines.append(f'    {loop_node}{{{{{self._sanitize_label(formatted_cond)}?}}}}:::loopStyle')
                mermaid_lines.append(f'    {current_node} --> {loop_node}')
                
                # Loop body
                body_stmts = stmt.get("body", [])
                if body_stmts:
                    last_body = self._build_flowchart_from_body(body_stmts, loop_node, mermaid_lines)
                    mermaid_lines.append(f'    {last_body} --> {loop_node}')
                else:
                    mermaid_lines.append(f'    {loop_body_node}["Loop Body"]:::processStyle')
                    mermaid_lines.append(f'    {loop_node} -->|Continue| {loop_body_node}')
                    mermaid_lines.append(f'    {loop_body_node} --> {loop_node}')
                
                mermaid_lines.append(f'    {exit_node}["Exit Loop"]:::processStyle')
                mermaid_lines.append(f'    {loop_node} -->|Done| {exit_node}')
                current_node = exit_node
                
            elif stmt_type == "return":
                # Handle return statement
                return_node = self._generate_node_id("Return")
                value = stmt.get("value", "")
                label = self._format_return_label(value)
                mermaid_lines.append(f'    {return_node}["{label}"]:::returnStyle')
                mermaid_lines.append(f'    {current_node} --> {return_node}')
                mermaid_lines.append(f'    {return_node} --> End')
                current_node = return_node
                
            elif stmt_type == "break":
                break_node = self._generate_node_id("Break")
                mermaid_lines.append(f'    {break_node}["⚠️ Break Loop"]:::controlStyle')
                mermaid_lines.append(f'    {current_node} --> {break_node}')
                current_node = break_node
                
            elif stmt_type == "continue":
                continue_node = self._generate_node_id("Continue")
                mermaid_lines.append(f'    {continue_node}["↻ Continue"]:::controlStyle')
                mermaid_lines.append(f'    {current_node} --> {continue_node}')
                current_node = continue_node
                
            elif stmt_type == "assignment":
                assign_node = self._generate_node_id("Assign")
                targets = stmt.get("targets", [])
                value = stmt.get("value", "")
                target_str = ", ".join(str(t) for t in targets) if targets else "variable"
                label = f"{target_str} = {self._sanitize_label(str(value))}"
                mermaid_lines.append(f'    {assign_node}["{label}"]:::processStyle')
                mermaid_lines.append(f'    {current_node} --> {assign_node}')
                current_node = assign_node
                
            elif stmt_type == "call":
                call_node = self._generate_node_id("Call")
                function = stmt.get("function", "")
                label = f"Call {self._sanitize_label(str(function))}"
                mermaid_lines.append(f'    {call_node}["{label}"]:::processStyle')
                mermaid_lines.append(f'    {current_node} --> {call_node}')
                current_node = call_node
        
        return current_node

    @cached_diagram('flowchart')
    def build(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        if not parsed_data or "functions" not in parsed_data:
            return {"error": "Invalid parsed data for flowchart."}

        self.node_counter = 0
        mermaid_lines = []
        mermaid_lines.append("flowchart TD")
        
        # Start node
        start_id = "Start"
        mermaid_lines.append(f'    {start_id}([Start]):::startEndStyle')
        prev_node = start_id

        functions = parsed_data.get("functions", [])
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
                mermaid_lines.append(f'    {prev_node} --> {summary_node}')
                prev_node = summary_node
        
        # Process each function or main block
        for func_idx, func in enumerate(functions):
            func_name = func.get('name', 'function')
            body = func.get("body", [])
            args = func.get("args", [])
            
            # If function has detailed body, use it
            if body:
                # Add function entry node (except for main)
                if func_name != "main":
                    func_node = self._generate_node_id("Func")
                    label = self._generate_semantic_label(func_name, "process")
                    mermaid_lines.append(f'    {func_node}["{label}"]:::functionStyle')
                    mermaid_lines.append(f'    {prev_node} --> {func_node}')
                    prev_node = func_node
                
                # Add input parameters if any
                if args and func_name != "main":
                    input_node = self._generate_node_id("Input")
                    args_str = ", ".join(str(a) for a in args)
                    mermaid_lines.append(f'    {input_node}[/"📥 Input: {args_str}"/]:::inputStyle')
                    mermaid_lines.append(f'    {prev_node} --> {input_node}')
                    prev_node = input_node
                
                # Build flowchart from detailed body
                prev_node = self._build_flowchart_from_body(body, prev_node, mermaid_lines)
                
            else:
                # Fallback to old method if no detailed body available
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
                            mermaid_lines.append(f'    {init_id}[/"📥 Get Input"/]:::inputStyle')
                        else:
                            mermaid_lines.append(f'    {init_id}["Initialization"]:::processStyle')
                        mermaid_lines.append(f'    {prev_node} --> {init_id}')
                        prev_node = init_id
                    
                    # Processing step (if there are operations beyond I/O)
                    if processing_calls:
                        proc_id = self._generate_node_id("Proc")
                        # Use NLP to generate semantic label
                        if self.nlp and processing_calls:
                            first_call = processing_calls[0]
                            op_type = self._extract_operation_type(first_call)
                            label = self._generate_semantic_label(first_call, op_type)
                            mermaid_lines.append(f'    {proc_id}["{label}"]:::processStyle')
                        else:
                            mermaid_lines.append(f'    {proc_id}["Processing Data"]:::processStyle')
                        mermaid_lines.append(f'    {prev_node} --> {proc_id}')
                        prev_node = proc_id
                    
                    # Control flow structures
                    for ctrl in control_flows:
                        ctrl_id = self._generate_node_id("Ctrl")
                        mermaid_lines.append(f'    {ctrl_id}{{{{{ctrl} Condition}}}}:::decisionStyle')
                        mermaid_lines.append(f'    {prev_node} --> {ctrl_id}')
                        
                        # Add True/False branches for decisions
                        if ctrl == "If":
                            true_id = self._generate_node_id("True")
                            false_id = self._generate_node_id("False")
                            mermaid_lines.append(f'    {true_id}["True Branch"]:::processStyle')
                            mermaid_lines.append(f'    {false_id}["False Branch"]:::processStyle')
                            mermaid_lines.append(f'    {ctrl_id} -->|Yes| {true_id}')
                            mermaid_lines.append(f'    {ctrl_id} -->|No| {false_id}')
                            
                            # Merge back
                            merge_id = self._generate_node_id("Merge")
                            mermaid_lines.append(f'    {merge_id}["Continue"]:::processStyle')
                            mermaid_lines.append(f'    {true_id} --> {merge_id}')
                            mermaid_lines.append(f'    {false_id} --> {merge_id}')
                            prev_node = merge_id
                        elif ctrl in ["For", "While"]:
                            loop_body = self._generate_node_id("Loop")
                            mermaid_lines.append(f'    {loop_body}["Loop Body"]:::processStyle')
                            mermaid_lines.append(f'    {ctrl_id} -->|Continue| {loop_body}')
                            mermaid_lines.append(f'    {loop_body} --> {ctrl_id}')
                            
                            exit_id = self._generate_node_id("Exit")
                            mermaid_lines.append(f'    {exit_id}["Exit Loop"]:::processStyle')
                            mermaid_lines.append(f'    {ctrl_id} -->|Done| {exit_id}')
                            prev_node = exit_id
                        else:
                            prev_node = ctrl_id
                    
                    # Output step
                    if has_output:
                        out_id = self._generate_node_id("Out")
                        mermaid_lines.append(f'    {out_id}[/"📤 Output Result"/]:::inputStyle')
                        mermaid_lines.append(f'    {prev_node} --> {out_id}')
                        prev_node = out_id
                            
                else:
                    # For defined functions - use NLP to understand and label
                    func_id = self._generate_node_id("Func")
                    label = self._generate_semantic_label(func_name, "process")
                    mermaid_lines.append(f'    {func_id}["{label}"]:::functionStyle')
                    mermaid_lines.append(f'    {prev_node} --> {func_id}')
                    prev_node = func_id
                    
                    # Show function internals using NLP analysis
                    statements = self._analyze_code_statements(func)
                    for stmt in statements:
                        stmt_id = self._generate_node_id("Stmt")
                        label = self._sanitize_label(stmt["label"])
                        
                        if stmt["type"] == "decision":
                            mermaid_lines.append(f'    {stmt_id}{{{{{label}}}}}')
                        elif stmt["type"] == "output" or stmt["type"] == "input":
                            mermaid_lines.append(f'    {stmt_id}[/"{label}"/]')
                        else:
                            mermaid_lines.append(f'    {stmt_id}["{label}"]')
                        
                        mermaid_lines.append(f'    {prev_node} --> {stmt_id}')
                        prev_node = stmt_id

        # End node
        end_id = "End"
        mermaid_lines.append(f'    {end_id}([End]):::startEndStyle')
        mermaid_lines.append(f'    {prev_node} --> {end_id}')

        # Add Mermaid CSS styles
        mermaid_lines.append("")
        mermaid_lines.append(self._get_mermaid_styles())

        mermaid_code = "\n".join(mermaid_lines) + "\n"
        
        # Debug logging
        logger.info(f"Generated flowchart with {len(mermaid_lines)} lines")
        logger.debug(f"First 500 chars of mermaid: {mermaid_code[:500]}")

        return {
            "language": parsed_data.get("language", "unknown"),
            "mermaid": mermaid_code
        }
