"""
Tests for API endpoints.
"""
import pytest
from fastapi.testclient import TestClient


class TestAnalyzeEndpoint:
    """Test cases for /api/analyze endpoint."""
    
    def test_analyze_python_code(self, client):
        """Test analyzing Python code."""
        response = client.post(
            "/api/analyze",
            json={
                "filename": "test.py",
                "content": "def add(a, b):\n    return a + b"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "language" in data
        assert data["language"] == "python"
        assert "flowchart" in data
        assert "workflow" in data
    
    def test_analyze_empty_code(self, client):
        """Test analyzing empty code."""
        response = client.post(
            "/api/analyze",
            json={
                "filename": "test.py",
                "content": ""
            }
        )
        
        assert response.status_code == 400
        assert "Empty code" in response.json()["detail"]
    
    def test_analyze_code_too_large(self, client):
        """Test analyzing code that exceeds size limit."""
        large_code = "x = 1\n" * 100000  # Exceeds MAX_CODE_LENGTH
        response = client.post(
            "/api/analyze",
            json={
                "filename": "test.py",
                "content": large_code
            }
        )
        
        assert response.status_code == 413
        assert "too large" in response.json()["detail"]
    
    def test_analyze_javascript_code(self, client):
        """Test analyzing JavaScript code."""
        response = client.post(
            "/api/analyze",
            json={
                "filename": "test.js",
                "content": "function hello() { return 'world'; }"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["language"] == "javascript"


class TestFlowchartEndpoint:
    """Test cases for /api/flowchart endpoint."""
    
    def test_flowchart_generation(self, client):
        """Test flowchart generation."""
        response = client.post(
            "/api/flowchart",
            json={
                "filename": "test.py",
                "content": "def test():\n    x = 1\n    return x"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "flowchart" in data


class TestWorkflowEndpoint:
    """Test cases for /api/workflow endpoint."""
    
    def test_workflow_generation(self, client):
        """Test workflow generation."""
        response = client.post(
            "/api/workflow",
            json={
                "filename": "test.py",
                "content": "def test():\n    x = 1\n    return x"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "workflow" in data


class TestRateLimiting:
    """Test cases for rate limiting."""
    
    @pytest.mark.skip(reason="Rate limiting requires real-time testing")
    def test_rate_limit_exceeded(self, client):
        """Test that rate limiting works after 20 requests."""
        # Make 21 requests
        for i in range(21):
            response = client.post(
                "/api/analyze",
                json={
                    "filename": "test.py",
                    "content": f"x = {i}"
                }
            )
            
            if i < 20:
                assert response.status_code == 200
            else:
                assert response.status_code == 429  # Too Many Requests
