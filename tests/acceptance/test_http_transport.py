"""
Test cases for HTTP transport functionality.

Tests the FastAPI-based HTTP server implementation of the MCP protocol.
"""

import asyncio
import json
import pytest
import httpx
from fastapi.testclient import TestClient

from datetime_mcp_server.http_server import app


class TestHTTPTransport:
    """Test HTTP transport functionality."""

    def setup_method(self):
        """Set up test client."""
        self.client = TestClient(app)

    def test_root_endpoint(self):
        """Test root endpoint returns basic information."""
        response = self.client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Datetime MCP Server"
        assert data["version"] == "0.1.0"
        assert data["transport"] == "http"
        assert "endpoints" in data

    def test_health_check(self):
        """Test health check endpoint."""
        response = self.client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"
        assert data["transport"] == "http"
        assert "uptime_seconds" in data
        assert "timestamp" in data

    def test_metrics_endpoint(self):
        """Test metrics endpoint returns Prometheus format."""
        response = self.client.get("/metrics")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/plain; charset=utf-8"
        content = response.text
        assert "datetime_mcp_requests_total" in content
        assert "datetime_mcp_response_time_seconds" in content
        assert "datetime_mcp_uptime_seconds" in content

    def test_mcp_tools_list(self):
        """Test MCP tools/list endpoint."""
        request_data = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": 1
        }
        response = self.client.post("/mcp", json=request_data)
        assert response.status_code == 200
        data = response.json()
        
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 1
        assert "result" in data
        assert "tools" in data["result"]
        
        tools = data["result"]["tools"]
        tool_names = [tool["name"] for tool in tools]
        expected_tools = [
            "add-note", "get-note", "list-notes", "delete-note",
            "get-current-datetime", "format-date", "calculate-date",
            "calculate-date-range", "calculate-business-days"
        ]
        for expected_tool in expected_tools:
            assert expected_tool in tool_names

    def test_mcp_tools_call(self):
        """Test MCP tools/call endpoint."""
        request_data = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "get-current-datetime",
                "arguments": {"format": "iso"}
            },
            "id": 2
        }
        response = self.client.post("/mcp", json=request_data)
        assert response.status_code == 200
        data = response.json()
        
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 2
        assert "result" in data
        assert "content" in data["result"]
        assert len(data["result"]["content"]) == 1
        assert data["result"]["content"][0]["type"] == "text"
        assert len(data["result"]["content"][0]["text"]) > 0

    def test_mcp_resources_list(self):
        """Test MCP resources/list endpoint."""
        request_data = {
            "jsonrpc": "2.0",
            "method": "resources/list",
            "id": 3
        }
        response = self.client.post("/mcp", json=request_data)
        assert response.status_code == 200
        data = response.json()
        
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 3
        assert "result" in data
        assert "resources" in data["result"]
        
        resources = data["result"]["resources"]
        resource_uris = [resource["uri"] for resource in resources]
        expected_resources = [
            "datetime://current", "datetime://today", "datetime://time",
            "datetime://timezone-info", "datetime://supported-timezones"
        ]
        for expected_resource in expected_resources:
            assert expected_resource in resource_uris

    def test_mcp_resources_read(self):
        """Test MCP resources/read endpoint."""
        request_data = {
            "jsonrpc": "2.0",
            "method": "resources/read",
            "params": {
                "uri": "datetime://current"
            },
            "id": 4
        }
        response = self.client.post("/mcp", json=request_data)
        assert response.status_code == 200
        data = response.json()
        
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 4
        assert "result" in data
        assert "contents" in data["result"]
        assert len(data["result"]["contents"]) == 1
        assert data["result"]["contents"][0]["uri"] == "datetime://current"
        assert len(data["result"]["contents"][0]["text"]) > 0

    def test_mcp_prompts_list(self):
        """Test MCP prompts/list endpoint."""
        request_data = {
            "jsonrpc": "2.0",
            "method": "prompts/list",
            "id": 5
        }
        response = self.client.post("/mcp", json=request_data)
        assert response.status_code == 200
        data = response.json()
        
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 5
        assert "result" in data
        assert "prompts" in data["result"]
        
        prompts = data["result"]["prompts"]
        prompt_names = [prompt["name"] for prompt in prompts]
        expected_prompts = [
            "summarize-notes", "schedule-event", "datetime-calculation-guide",
            "business-day-rules", "timezone-best-practices"
        ]
        for expected_prompt in expected_prompts:
            assert expected_prompt in prompt_names

    def test_mcp_error_handling(self):
        """Test MCP error handling for invalid requests."""
        # Test missing method
        request_data = {
            "jsonrpc": "2.0",
            "id": 6
        }
        response = self.client.post("/mcp", json=request_data)
        assert response.status_code == 400
        
        # Test unknown method
        request_data = {
            "jsonrpc": "2.0",
            "method": "unknown/method",
            "id": 7
        }
        response = self.client.post("/mcp", json=request_data)
        assert response.status_code == 404
        
        # Test invalid JSON
        response = self.client.post("/mcp", content="invalid json", headers={"content-type": "application/json"})
        assert response.status_code == 400

    def test_sse_stream_endpoint(self):
        """Test Server-Sent Events streaming endpoint."""
        # Note: This is a basic test for SSE endpoint existence
        # Full streaming tests would require more complex async testing
        with self.client.stream("GET", "/mcp/stream") as response:
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
            assert "cache-control" in response.headers
            assert response.headers["cache-control"] == "no-cache"

    def test_cors_headers(self):
        """Test CORS headers are present."""
        response = self.client.options("/mcp")
        assert response.status_code == 200
        # CORS headers should be present for all origins
        response = self.client.get("/", headers={"Origin": "http://localhost:3000"})
        assert "access-control-allow-origin" in response.headers

    def test_metrics_middleware(self):
        """Test that metrics middleware is working."""
        # Make a request to generate metrics
        self.client.get("/health")
        
        # Check metrics are updated
        response = self.client.get("/metrics")
        content = response.text
        
        # Should have at least 1 request recorded
        assert "datetime_mcp_requests_total" in content
        # Response time should be recorded
        assert "datetime_mcp_response_time_seconds" in content 