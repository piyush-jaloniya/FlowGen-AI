import pytest
from app.services.identifier_formatter import IdentifierFormatter, humanize_identifier, detect_operation_type


class TestIdentifierFormatter:
    """Test cases for IdentifierFormatter class."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.formatter = IdentifierFormatter(nlp=None)
    
    # Basic Conversion Tests
    def test_camel_case(self):
        """Test camelCase conversion."""
        assert self.formatter.humanize_identifier("calculateSum") == "Calculate Sum"
        assert self.formatter.humanize_identifier("getUserData") == "Get User Data"
        assert self.formatter.humanize_identifier("isValid") == "Is Valid"
    
    def test_snake_case(self):
        """Test snake_case conversion."""
        assert self.formatter.humanize_identifier("calculate_sum") == "Calculate Sum"
        assert self.formatter.humanize_identifier("get_user_data") == "Get User Data"
        assert self.formatter.humanize_identifier("is_valid") == "Is Valid"
    
    def test_pascal_case(self):
        """Test PascalCase conversion."""
        assert self.formatter.humanize_identifier("CalculateSum") == "Calculate Sum"
        assert self.formatter.humanize_identifier("GetUserData") == "Get User Data"
        assert self.formatter.humanize_identifier("IsValid") == "Is Valid"
    
    # Acronym Tests
    def test_acronyms(self):
        """Test acronym preservation."""
        assert self.formatter.humanize_identifier("HTTPRequest") == "HTTP Request"
        assert self.formatter.humanize_identifier("getHTTPURL") == "Get HTTP URL"
        assert self.formatter.humanize_identifier("parseJSONData") == "Parse JSON Data"
        assert self.formatter.humanize_identifier("fetchAPIData") == "Fetch API Data"
    
    # Number Tests
    def test_numbers(self):
        """Test handling of numbers in identifiers."""
        assert self.formatter.humanize_identifier("calculate2D") == "Calculate 2 D"
        assert self.formatter.humanize_identifier("get3DCoordinates") == "Get 3 D Coordinates"
        assert self.formatter.humanize_identifier("array2String") == "Array 2 String"
    
    # Mixed Case Tests
    def test_mixed_cases(self):
        """Test complex mixed cases."""
        assert self.formatter.humanize_identifier("getHTTP2Protocol") == "Get HTTP 2 Protocol"
        assert self.formatter.humanize_identifier("parseXMLToJSON") == "Parse XML To JSON"
    
    # Edge Cases
    def test_empty_string(self):
        """Test empty string handling."""
        assert self.formatter.humanize_identifier("") == "Process"
        assert self.formatter.humanize_identifier(None) == "Process"
    
    def test_single_word(self):
        """Test single word identifiers."""
        assert self.formatter.humanize_identifier("calculate") == "Calculate"
        assert self.formatter.humanize_identifier("sum") == "Sum"
    
    def test_all_caps(self):
        """Test all caps identifiers."""
        assert self.formatter.humanize_identifier("HTTP") == "HTTP"
        assert self.formatter.humanize_identifier("API") == "API"
    
    # Semantic Prefix Tests
    def test_output_prefix(self):
        """Test output operation prefix."""
        result = self.formatter.humanize_identifier("result", operation_type="output")
        assert result == "Display Result"
        
        # Should not add prefix if already present
        result = self.formatter.humanize_identifier("displayResult", operation_type="output")
        assert result == "Display Result"
    
    def test_input_prefix(self):
        """Test input operation prefix."""
        result = self.formatter.humanize_identifier("userData", operation_type="input")
        assert result == "Get User Data"
        
        result = self.formatter.humanize_identifier("getUserData", operation_type="input")
        assert result == "Get User Data"
    
    def test_calculation_prefix(self):
        """Test calculation operation prefix."""
        result = self.formatter.humanize_identifier("sum", operation_type="calculation")
        assert result == "Calculate Sum"
        
        result = self.formatter.humanize_identifier("calculateSum", operation_type="calculation")
        assert result == "Calculate Sum"
    
    # Operation Type Detection Tests
    def test_detect_output_operations(self):
        """Test detection of output operations."""
        assert self.formatter.detect_operation_type("print") == "output"
        assert self.formatter.detect_operation_type("displayResult") == "output"
        assert self.formatter.detect_operation_type("showData") == "output"
        assert self.formatter.detect_operation_type("console_log") == "output"
    
    def test_detect_input_operations(self):
        """Test detection of input operations."""
        assert self.formatter.detect_operation_type("input") == "input"
        assert self.formatter.detect_operation_type("getUserInput") == "input"
        assert self.formatter.detect_operation_type("readData") == "input"
        assert self.formatter.detect_operation_type("fetchData") == "input"
    
    def test_detect_calculation_operations(self):
        """Test detection of calculation operations."""
        assert self.formatter.detect_operation_type("calculateSum") == "calculation"
        assert self.formatter.detect_operation_type("computeAverage") == "calculation"
        assert self.formatter.detect_operation_type("sum") == "calculation"
        assert self.formatter.detect_operation_type("max") == "calculation"
    
    def test_detect_sort_operations(self):
        """Test detection of sort operations."""
        assert self.formatter.detect_operation_type("sortArray") == "data_sort"
        assert self.formatter.detect_operation_type("orderList") == "data_sort"
        assert self.formatter.detect_operation_type("reverse") == "data_sort"
    
    def test_detect_search_operations(self):
        """Test detection of search operations."""
        assert self.formatter.detect_operation_type("findElement") == "search"
        assert self.formatter.detect_operation_type("searchData") == "search"
        assert self.formatter.detect_operation_type("locateItem") == "search"
    
    def test_detect_default_operation(self):
        """Test default operation type for unknown operations."""
        assert self.formatter.detect_operation_type("doSomething") == "process"
        assert self.formatter.detect_operation_type("handleEvent") == "process"


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_humanize_identifier_function(self):
        """Test humanize_identifier convenience function."""
        assert humanize_identifier("calculateSum") == "Calculate Sum"
        assert humanize_identifier("get_user_data") == "Get User Data"
    
    def test_detect_operation_type_function(self):
        """Test detect_operation_type convenience function."""
        assert detect_operation_type("print") == "output"
        assert detect_operation_type("calculateSum") == "calculation"


# Integration Tests
class TestRealWorldExamples:
    """Test with real-world function names."""
    
    def setup_method(self):
        self.formatter = IdentifierFormatter(nlp=None)
    
    def test_python_functions(self):
        """Test common Python function names."""
        assert self.formatter.humanize_identifier("__init__") == "Init"
        assert self.formatter.humanize_identifier("to_string") == "To String"
        assert self.formatter.humanize_identifier("is_empty") == "Is Empty"
    
    def test_javascript_functions(self):
        """Test common JavaScript function names."""
        assert self.formatter.humanize_identifier("getElementById") == "Get Element By ID"
        assert self.formatter.humanize_identifier("addEventListener") == "Add Event Listener"
        assert self.formatter.humanize_identifier("querySelector") == "Query Selector"
    
    def test_java_methods(self):
        """Test common Java method names."""
        assert self.formatter.humanize_identifier("toString") == "To String"
        assert self.formatter.humanize_identifier("equals") == "Equals"
        assert self.formatter.humanize_identifier("hashCode") == "Hash Code"
