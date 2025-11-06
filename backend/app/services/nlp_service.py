import re
from typing import Dict, Any, List, Optional
import spacy


class NLPService:
    """
    Combines heuristic labeling + spaCy NLP summarization.
    Lightweight, works offline; ready for future model integration.
    """

    def __init__(self):
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            raise RuntimeError(
                "spaCy model not found. Run: python -m spacy download en_core_web_sm"
            )

    # ----------------------------------------------------------------------
    # 1️⃣ Identifier humanization (for variable/function names)
    # ----------------------------------------------------------------------
    def humanize_identifier(self, name: str) -> str:
        """Convert snake_case or camelCase to human-readable text."""
        if not name:
            return ""
        s1 = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
        s2 = s1.replace("_", " ")
        return s2.strip().capitalize()

    # ----------------------------------------------------------------------
    # 2️⃣ Generate short function label (for flowchart node)
    # ----------------------------------------------------------------------
    def generate_short_label(self, func: Dict[str, Any]) -> str:
        """Create a concise label for a function node."""
        doc = func.get("docstring") or ""
        if doc:
            label = doc.strip().splitlines()[0]
            if len(label) > 80:
                label = label[:77] + "..."
            return label
        return self.humanize_identifier(func.get("name", "function"))

    # ----------------------------------------------------------------------
    # 3️⃣ Generate full descriptive text (for workflow/tooltip)
    # ----------------------------------------------------------------------
    def generate_full_text(self, func: Dict[str, Any]) -> str:
        """Generate full sentence describing what the function does."""
        name = func.get("name")
        args = func.get("args", []) or []
        calls = func.get("calls", []) or []
        controls = func.get("control_flow", []) or []

        parts = [f"Function `{name}`"]
        if args:
            parts.append(f"takes arguments {', '.join(args)}")
        if controls:
            parts.append(f"contains control constructs: {', '.join(controls)}")
        if calls:
            parts.append(f"calls functions: {', '.join(calls)}")
        if func.get("docstring"):
            parts.append(f"Doc: {func.get('docstring').strip().splitlines()[0]}")

        return ". ".join(parts) + "."

    # ----------------------------------------------------------------------
    # 4️⃣ NLP summarization using spaCy
    # ----------------------------------------------------------------------
    def summarize_function(self, name: str, calls: List[str], control_flow: List[str]) -> str:
        """Use spaCy to build a short semantic summary."""
        doc = self.nlp(name.replace("_", " "))
        func_action = " ".join(
            [token.lemma_ for token in doc if token.pos_ in ("VERB", "NOUN")]
        )

        summary_parts = []
        if func_action:
            summary_parts.append(f"The function '{name}' is used to {func_action}.")
        else:
            summary_parts.append(f"The function '{name}' performs an operation.")

        if control_flow:
            summary_parts.append(
                f"It includes control structures such as {', '.join(control_flow)}."
            )
        if calls:
            summary_parts.append(f"It calls other functions like {', '.join(calls[:3])}.")

        return " ".join(summary_parts)

    # ----------------------------------------------------------------------
    # 5️⃣ Summarize entire parsed code (batch)
    # ----------------------------------------------------------------------
    def summarize_code(self, parsed_data: Dict[str, Any]) -> List[Dict[str, str]]:
        """Generate summaries for all functions in parsed data."""
        summaries = []
        for func in parsed_data.get("functions", []):
            summary = self.summarize_function(
                name=func.get("name", "unknown_function"),
                calls=func.get("calls", []),
                control_flow=func.get("control_flow", []),
            )
            summaries.append({
                "function": func.get("name"),
                "summary": summary,
                "label": self.generate_short_label(func),
                "description": self.generate_full_text(func),
            })
        return summaries

    # ----------------------------------------------------------------------
    # 6️⃣ Placeholder for LLM-based rephrasing
    # ----------------------------------------------------------------------
    def refine_with_model(self, text: str) -> str:
        """In production: call GPT / CodeT5 for smarter phrasing."""
        return text
