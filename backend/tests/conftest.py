"""
Test configuration and fixtures for FlowGen AI tests.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.parser_service import ParserService
from app.services.nlp_service import NLPService
from app.services.flowchart_service import FlowchartService
from app.services.workflow_service import WorkflowService
from app.services.llm_service import LLMService


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def parser_service():
    """Parser service instance."""
    return ParserService()


@pytest.fixture
def nlp_service():
    """NLP service instance."""
    return NLPService()


@pytest.fixture
def flowchart_service(parser_service, nlp_service):
    """Flowchart service instance."""
    return FlowchartService(parser_service, nlp_service.nlp)


@pytest.fixture
def workflow_service(parser_service, nlp_service):
    """Workflow service instance."""
    return WorkflowService(parser_service, nlp_service.nlp)


@pytest.fixture
def llm_service():
    """LLM service instance."""
    return LLMService()


@pytest.fixture
def sample_python_code():
    """Sample Python code for testing."""
    return """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

def main():
    result = fibonacci(10)
    print(f"Result: {result}")

if __name__ == "__main__":
    main()
"""


@pytest.fixture
def sample_javascript_code():
    """Sample JavaScript code for testing."""
    return """
function factorial(n) {
    if (n <= 1) return 1;
    return n * factorial(n - 1);
}

const result = factorial(5);
console.log(result);
"""


@pytest.fixture
def sample_java_code():
    """Sample Java code for testing."""
    return """
public class BubbleSort {
    public static void bubbleSort(int[] arr) {
        int n = arr.length;
        for (int i = 0; i < n-1; i++) {
            for (int j = 0; j < n-i-1; j++) {
                if (arr[j] > arr[j+1]) {
                    int temp = arr[j];
                    arr[j] = arr[j+1];
                    arr[j+1] = temp;
                }
            }
        }
    }
}
"""
