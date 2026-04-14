import re
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class IdentifierFormatter:
    """
    Utility class for formatting code identifiers (function names, variables)
    into human-readable labels with NLP support.
    """
    
    def __init__(self, nlp=None):
        """
        Initialize the formatter.
        
        Args:
            nlp: Optional spaCy NLP model for semantic analysis
        """
        self.nlp = nlp
        
        # Common acronyms to preserve
        self.acronyms = {
            'HTTP', 'HTTPS', 'API', 'URL', 'URI', 'HTML', 'CSS', 'JS',
            'SQL', 'XML', 'JSON', 'CSV', 'PDF', 'ID', 'UUID', 'IO',
            'CPU', 'GPU', 'RAM', 'DB', 'UI', 'UX', 'CLI', 'GUI'
        }
    
    def humanize_identifier(self, identifier: str, operation_type: Optional[str] = None) -> str:
        """
        Convert a code identifier to human-readable text.
        
        Args:
            identifier: The identifier to humanize (e.g., 'calculateSum', 'get_user_data')
            operation_type: Optional operation type for semantic context
            
        Returns:
            Human-readable label
            
        Examples:
            'calculateSum' -> 'Calculate Sum'
            'get_user_data' -> 'Get User Data'
            'HTTPRequest' -> 'HTTP Request'
            'calculate2DArea' -> 'Calculate 2D Area'
        """
        if not identifier:
            return "Process"
        
        # Step 1: Basic conversion
        readable = self._convert_to_readable(identifier)
        
        # Step 2: Use NLP for semantic enhancement (if available)
        if self.nlp:
            readable = self._enhance_with_nlp(readable, operation_type)
        
        # Step 3: Add semantic prefix based on operation type
        if operation_type:
            readable = self._add_semantic_prefix(readable, operation_type)
        
        return readable
    
    def _convert_to_readable(self, identifier: str) -> str:
        """
        Convert identifier from camelCase/snake_case/PascalCase to readable text.
        
        Handles:
        - camelCase: calculateSum -> Calculate Sum
        - snake_case: get_user_data -> Get User Data
        - PascalCase: HTTPRequest -> HTTP Request
        - Numbers: calculate2D -> Calculate 2D
        - Acronyms: getHTTPURL -> Get HTTP URL
        """
        # Preserve known acronyms
        text = identifier
        for acronym in self.acronyms:
            # Replace acronym with placeholder to preserve it
            text = re.sub(f'({acronym})', r'_\1_', text, flags=re.IGNORECASE)
        
        # Handle numbers: insert space before numbers
        text = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', text)
        text = re.sub(r'(\d)([a-zA-Z])', r'\1 \2', text)
        
        # Handle camelCase and PascalCase
        # Insert space before uppercase letters that follow lowercase
        text = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', text)
        
        # Handle consecutive uppercase letters (acronyms)
        # HTTPRequest -> HTTP Request
        text = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', text)
        
        # Handle snake_case
        text = text.replace('_', ' ')
        
        # Clean up multiple spaces
        text = re.sub(r'\s+', ' ', text)
        
        # Capitalize words properly
        words = text.split()
        capitalized_words = []
        
        for word in words:
            # Check if it's an acronym (all uppercase)
            if word.upper() in self.acronyms:
                capitalized_words.append(word.upper())
            # Check if it's a number
            elif word.isdigit() or re.match(r'^\d+[A-Z]$', word):
                capitalized_words.append(word.upper())
            else:
                capitalized_words.append(word.capitalize())
        
        return ' '.join(capitalized_words)
    
    def _enhance_with_nlp(self, text: str, operation_type: Optional[str]) -> str:
        """
        Use NLP to extract and reconstruct text with better semantics.
        
        Args:
            text: Human-readable text
            operation_type: Operation type hint
            
        Returns:
            Enhanced text
        """
        try:
            doc = self.nlp(text)
            
            # Extract verbs and nouns
            verbs = [token.lemma_.capitalize() for token in doc if token.pos_ == "VERB"]
            nouns = [token.text.capitalize() for token in doc if token.pos_ == "NOUN"]
            
            # Reconstruct based on extracted parts
            if verbs and nouns:
                # Verb + Nouns pattern (e.g., "Calculate Sum Total")
                return f"{verbs[0]} {' '.join(nouns)}"
            elif verbs:
                # Just verb (e.g., "Calculate")
                return verbs[0]
            elif nouns:
                # Just nouns (e.g., "User Data")
                return ' '.join(nouns)
                
        except Exception as e:
            logger.debug(f"NLP enhancement failed: {e}")
        
        return text
    
    def _add_semantic_prefix(self, text: str, operation_type: str) -> str:
        """
        Add semantic prefix based on operation type.
        
        Args:
            text: Current text
            operation_type: Type of operation
            
        Returns:
            Text with appropriate prefix
        """
        text_lower = text.lower()
        
        # Output operations
        if operation_type == "output":
            if not text_lower.startswith(("print", "display", "output", "show", "write")):
                return f"Display {text}"
        
        # Input operations
        elif operation_type == "input":
            if not text_lower.startswith(("get", "read", "input", "fetch", "load")):
                return f"Get {text}"
        
        # Calculation operations
        elif operation_type in ("calculation", "calc"):
            if not text_lower.startswith(("calculate", "compute", "evaluate")):
                return f"Calculate {text}"
        
        # Sorting operations
        elif operation_type in ("data_sort", "sort"):
            if not text_lower.startswith(("sort", "order", "arrange")):
                return f"Sort {text}"
        
        # Search operations
        elif operation_type == "search":
            if not text_lower.startswith(("find", "search", "locate", "lookup")):
                return f"Find {text}"
        
        return text
    
    def detect_operation_type(self, identifier: str) -> str:
        """
        Detect the operation type from an identifier.
        
        Args:
            identifier: Function or method name
            
        Returns:
            Operation type string
        """
        identifier_lower = identifier.lower()
        
        # I/O Operations
        if any(keyword in identifier_lower for keyword in 
               ["print", "println", "printf", "cout", "console", "log", "write", "display", "show", "output"]):
            return "output"
        
        if any(keyword in identifier_lower for keyword in 
               ["input", "scanf", "cin", "read", "readline", "gets", "getline", "fetch", "load"]):
            return "input"
        
        # Data Operations
        if any(keyword in identifier_lower for keyword in 
               ["append", "push", "add", "insert", "extend"]):
            return "data_add"
        
        if any(keyword in identifier_lower for keyword in 
               ["pop", "remove", "delete", "clear", "erase"]):
            return "data_remove"
        
        if any(keyword in identifier_lower for keyword in 
               ["sort", "sorted", "reverse", "order", "arrange"]):
            return "data_sort"
        
        if any(keyword in identifier_lower for keyword in 
               ["find", "search", "index", "contains", "lookup", "locate"]):
            return "search"
        
        # Mathematical Operations
        if any(keyword in identifier_lower for keyword in 
               ["sum", "total", "count", "max", "min", "avg", "average", "abs", "pow", "sqrt", 
                "calculate", "compute", "evaluate"]):
            return "calculation"
        
        # Use NLP for deeper analysis
        if self.nlp:
            try:
                doc = self.nlp(identifier)
                for token in doc:
                    if token.pos_ == "VERB":
                        lemma = token.lemma_.lower()
                        if lemma in ["print", "display", "show", "output"]:
                            return "output"
                        elif lemma in ["read", "get", "input", "fetch"]:
                            return "input"
                        elif lemma in ["calculate", "compute", "evaluate"]:
                            return "calculation"
                        elif lemma in ["sort", "order", "arrange"]:
                            return "data_sort"
                        elif lemma in ["search", "find", "locate"]:
                            return "search"
            except Exception as e:
                logger.debug(f"NLP operation detection failed: {e}")
        
        return "process"


# Convenience functions for backward compatibility
def humanize_identifier(identifier: str, nlp=None, operation_type: Optional[str] = None) -> str:
    """
    Convenience function to humanize an identifier.
    
    Args:
        identifier: The identifier to humanize
        nlp: Optional spaCy NLP model
        operation_type: Optional operation type
        
    Returns:
        Human-readable label
    """
    formatter = IdentifierFormatter(nlp=nlp)
    return formatter.humanize_identifier(identifier, operation_type)


def detect_operation_type(identifier: str, nlp=None) -> str:
    """
    Convenience function to detect operation type.
    
    Args:
        identifier: The identifier to analyze
        nlp: Optional spaCy NLP model
        
    Returns:
        Operation type string
    """
    formatter = IdentifierFormatter(nlp=nlp)
    return formatter.detect_operation_type(identifier)
