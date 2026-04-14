"""
Tests for ParserService - language detection and code parsing.
"""
import pytest
from app.services.parser_service import ParserService


class TestParserService:
    """Test cases for ParserService."""
    
    def test_detect_language_python(self, parser_service):
        """Test Python language detection."""
        code = "def hello():\n    print('Hello')"
        lang = parser_service.detect_language("test.py", code)
        assert lang == "python"
    
    def test_detect_language_javascript(self, parser_service):
        """Test JavaScript language detection."""
        code = "function hello() { console.log('Hello'); }"
        lang = parser_service.detect_language("test.js", code)
        assert lang == "javascript"
    
    def test_detect_language_java(self, parser_service):
        """Test Java language detection."""
        code = "public class Test { }"
        lang = parser_service.detect_language("Test.java", code)
        assert lang == "java"
    
    def test_detect_language_c(self, parser_service):
        """Test C language detection."""
        code = "#include <stdio.h>\nint main() { return 0; }"
        lang = parser_service.detect_language("test.c", code)
        assert lang == "c"
    
    def test_detect_language_cpp(self, parser_service):
        """Test C++ language detection."""
        code = "#include <iostream>\nint main() { return 0; }"
        lang = parser_service.detect_language("test.cpp", code)
        assert lang == "cpp"
    
    def test_parse_python_code(self, parser_service, sample_python_code):
        """Test parsing Python code."""
        parsed = parser_service.parse_code("python", "test.py", sample_python_code)
        
        assert parsed is not None
        assert "language" in parsed
        assert parsed["language"] == "python"
        assert "functions" in parsed
        assert len(parsed["functions"]) > 0
        
        # Check for fibonacci function
        func_names = [f["name"] for f in parsed["functions"]]
        assert "fibonacci" in func_names
        assert "main" in func_names
    
    def test_parse_javascript_code(self, parser_service, sample_javascript_code):
        """Test parsing JavaScript code."""
        parsed = parser_service.parse_code("javascript", "test.js", sample_javascript_code)
        
        assert parsed is not None
        assert "language" in parsed
        assert parsed["language"] == "javascript"
        assert "functions" in parsed
        
        # Check for factorial function
        func_names = [f["name"] for f in parsed["functions"]]
        assert "factorial" in func_names
    
    def test_parse_empty_code(self, parser_service):
        """Test parsing empty code."""
        parsed = parser_service.parse_code("python", "test.py", "")
        
        assert parsed is not None
        assert "functions" in parsed
        assert len(parsed["functions"]) == 0
    
    def test_parse_invalid_syntax(self, parser_service):
        """Test parsing code with invalid syntax."""
        invalid_code = "def broken(\n    print('missing closing paren'"
        parsed = parser_service.parse_code("python", "test.py", invalid_code)
        
        # Should handle gracefully
        assert parsed is not None
        assert "language" in parsed
