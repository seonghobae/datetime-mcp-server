"""HTTP transport implementation for the datetime MCP server."""

import asyncio
import json
import logging
import os
import platform
import signal
import sys
import threading
import time
import weakref
from typing import Any, Dict, Set
from collections import deque

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from hypercorn.asyncio import serve
from hypercorn.config import Config

# Use uvloop for better performance on Unix systems
if platform.system() != "Windows":
    try:
        import uvloop

        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    except ImportError:
        pass

from .server import (
    handle_list_resources,
    handle_read_resource,
    handle_list_prompts,
    handle_get_prompt,
    handle_list_tools,
    handle_call_tool,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Enhanced metrics storage with better memory management
metrics_lock = threading.Lock()
MAX_RESPONSE_TIMES = 1000  # Limit response times storage
MAX_ENDPOINT_TRACKING = 100  # Limit tracked endpoints

# Use deque for efficient memory management
response_times_deque = deque(maxlen=MAX_RESPONSE_TIMES)

metrics = {
    "requests_total": 0,
    "requests_by_endpoint": {},
    "response_times": response_times_deque,
    "errors_total": 0,
    "start_time": time.time(),
    "concurrent_requests": 0,
    "max_concurrent_requests": 0,
}

# SSE connection tracking for better resource management
sse_connections_lock = threading.Lock()
sse_connections: Set[weakref.ref] = set()
max_sse_connections = 100


class SSEConnectionManager:
    """Manages SSE connections to prevent resource leaks."""

    def __init__(self, max_connections: int = 100):
        self.max_connections = max_connections
        self.connections: Set[str] = set()  # Use simple set instead of weak references
        self.lock = threading.Lock()
        self.connection_timestamps: Dict[str, float] = {}  # Track creation time

    def add_connection(self, connection_id: str) -> bool:
        """Add a new SSE connection. Returns False if max connections reached."""
        with self.lock:
            # Clean up old connections first
            self._cleanup_old_connections()

            if len(self.connections) >= self.max_connections:
                logger.warning(
                    f"Maximum SSE connections ({self.max_connections}) reached"
                )
                return False

            # Add connection to tracking
            self.connections.add(connection_id)
            self.connection_timestamps[connection_id] = time.time()
            logger.debug(
                f"Added SSE connection {connection_id}. Total connections: {len(self.connections)}"
            )
            return True

    def remove_connection(self, connection_id: str) -> None:
        """Remove an SSE connection."""
        with self.lock:
            if connection_id in self.connections:
                self.connections.discard(connection_id)
                self.connection_timestamps.pop(connection_id, None)
                logger.debug(
                    f"Removed SSE connection {connection_id}. Total connections: {len(self.connections)}"
                )

    def _cleanup_old_connections(self) -> None:
        """Clean up connections older than 6 hours."""
        current_time = time.time()
        max_age = 6 * 3600  # 6 hours in seconds

        old_connections = []
        for conn_id, timestamp in self.connection_timestamps.items():
            if current_time - timestamp > max_age:
                old_connections.append(conn_id)

        for conn_id in old_connections:
            self.connections.discard(conn_id)
            self.connection_timestamps.pop(conn_id, None)

        if old_connections:
            logger.debug(f"Cleaned up {len(old_connections)} old SSE connections")

    def get_connection_count(self) -> int:
        """Get current number of active connections."""
        with self.lock:
            self._cleanup_old_connections()
            return len(self.connections)

    def is_connection_active(self, connection_id: str) -> bool:
        """Check if a connection is still active."""
        with self.lock:
            return connection_id in self.connections


# Global SSE connection manager
sse_manager = SSEConnectionManager(max_sse_connections)


def update_metrics(endpoint: str, process_time: float, is_error: bool = False):
    """Thread-safe metrics update with memory management."""
    with metrics_lock:
        metrics["requests_total"] += 1

        # Limit endpoint tracking to prevent memory bloat
        if len(metrics["requests_by_endpoint"]) >= MAX_ENDPOINT_TRACKING:
            # Remove least frequently used endpoint
            min_endpoint = min(
                metrics["requests_by_endpoint"], key=metrics["requests_by_endpoint"].get
            )
            del metrics["requests_by_endpoint"][min_endpoint]
            logger.debug(
                f"Removed endpoint {min_endpoint} from tracking due to memory limits"
            )

        metrics["requests_by_endpoint"][endpoint] = (
            metrics["requests_by_endpoint"].get(endpoint, 0) + 1
        )

        if is_error:
            metrics["errors_total"] += 1

        # Use deque for automatic memory management
        response_times_deque.append(process_time)


def tool_to_dict(tool) -> Dict[str, Any]:
    """Convert Tool object to serializable dictionary."""
    return {
        "name": tool.name,
        "description": tool.description,
        "inputSchema": tool.inputSchema.model_dump()
        if hasattr(tool.inputSchema, "model_dump")
        else tool.inputSchema,
    }


def resource_to_dict(resource) -> Dict[str, Any]:
    """Convert Resource object to serializable dictionary."""
    return {
        "uri": str(resource.uri),
        "name": resource.name,
        "description": resource.description,
        "mimeType": resource.mimeType,
    }


def prompt_to_dict(prompt) -> Dict[str, Any]:
    """Convert Prompt object to serializable dictionary."""
    return {
        "name": prompt.name,
        "description": prompt.description,
        "arguments": [
            {"name": arg.name, "description": arg.description, "required": arg.required}
            for arg in (prompt.arguments or [])
        ],
    }


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Datetime MCP Server",
        description="MCP server for precise date/time calculations",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure as needed for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Enhanced middleware for metrics and performance monitoring
    @app.middleware("http")
    async def enhanced_metrics_middleware(request: Request, call_next):
        start_time = time.time()

        # Track concurrent requests
        with metrics_lock:
            metrics["concurrent_requests"] += 1
            if metrics["concurrent_requests"] > metrics["max_concurrent_requests"]:
                metrics["max_concurrent_requests"] = metrics["concurrent_requests"]

        endpoint = request.url.path

        try:
            response = await call_next(request)
            is_error = response.status_code >= 400
        except Exception as e:
            logger.error(f"Request failed: {e}")
            is_error = True
            raise
        finally:
            process_time = time.time() - start_time
            update_metrics(endpoint, process_time, is_error)

            # Decrement concurrent requests
            with metrics_lock:
                metrics["concurrent_requests"] -= 1

        response.headers["X-Process-Time"] = str(process_time)
        response.headers["X-Server"] = "hypercorn-datetime-mcp"
        return response

    return app


# Create the FastAPI app
app = create_app()


@app.get("/health")
async def health_check():
    """Enhanced health check endpoint with detailed metrics."""
    uptime = time.time() - metrics["start_time"]

    with metrics_lock:
        # Calculate metrics safely
        avg_response_time = (
            sum(metrics["response_times"]) / len(metrics["response_times"])
            if metrics["response_times"]
            else 0
        )

        # Get SSE connection info
        sse_count = sse_manager.get_connection_count()

        health_data = {
            "status": "healthy",
            "version": "0.1.0",
            "uptime_seconds": uptime,
            "timestamp": time.time(),
            "transport": "http",
            "server": "hypercorn",
            "performance": {
                "avg_response_time_ms": round(avg_response_time * 1000, 3),
                "total_requests": metrics["requests_total"],
                "error_rate": round(
                    metrics["errors_total"] / max(metrics["requests_total"], 1) * 100, 2
                ),
                "concurrent_requests": metrics["concurrent_requests"],
                "max_concurrent_requests": metrics["max_concurrent_requests"],
                "response_times_tracked": len(metrics["response_times"]),
            },
            "connections": {
                "active_sse_connections": sse_count,
                "max_sse_connections": max_sse_connections,
                "sse_utilization_percent": round(
                    (sse_count / max_sse_connections) * 100, 1
                ),
            },
            "memory": {
                "tracked_endpoints": len(metrics["requests_by_endpoint"]),
                "max_endpoint_tracking": MAX_ENDPOINT_TRACKING,
            },
        }

    return JSONResponse(health_data)


@app.get("/metrics")
async def get_metrics():
    """Enhanced metrics endpoint with SSE connection metrics."""
    uptime = time.time() - metrics["start_time"]
    sse_count = sse_manager.get_connection_count()

    with metrics_lock:
        avg_response_time = (
            sum(metrics["response_times"]) / len(metrics["response_times"])
            if metrics["response_times"]
            else 0
        )

        prometheus_metrics = f"""# HELP datetime_mcp_requests_total Total number of requests
# TYPE datetime_mcp_requests_total counter
datetime_mcp_requests_total {metrics["requests_total"]}

# HELP datetime_mcp_errors_total Total number of errors
# TYPE datetime_mcp_errors_total counter
datetime_mcp_errors_total {metrics["errors_total"]}

# HELP datetime_mcp_response_time_seconds Average response time
# TYPE datetime_mcp_response_time_seconds gauge
datetime_mcp_response_time_seconds {avg_response_time}

# HELP datetime_mcp_uptime_seconds Server uptime
# TYPE datetime_mcp_uptime_seconds gauge
datetime_mcp_uptime_seconds {uptime}

# HELP datetime_mcp_concurrent_requests Current concurrent requests
# TYPE datetime_mcp_concurrent_requests gauge
datetime_mcp_concurrent_requests {metrics["concurrent_requests"]}

# HELP datetime_mcp_max_concurrent_requests Maximum concurrent requests seen
# TYPE datetime_mcp_max_concurrent_requests gauge
datetime_mcp_max_concurrent_requests {metrics["max_concurrent_requests"]}

# HELP datetime_mcp_sse_connections Active SSE connections
# TYPE datetime_mcp_sse_connections gauge
datetime_mcp_sse_connections {sse_count}

# HELP datetime_mcp_tracked_endpoints Number of tracked endpoints
# TYPE datetime_mcp_tracked_endpoints gauge
datetime_mcp_tracked_endpoints {len(metrics["requests_by_endpoint"])}
"""

    return Response(content=prometheus_metrics, media_type="text/plain")


@app.post("/mcp")
async def mcp_endpoint(request: Request):
    """Main MCP endpoint for JSON-RPC over HTTP with improved error handling."""
    try:
        # Parse JSON-RPC request
        body = await request.json()

        method = body.get("method")
        params = body.get("params", {})
        request_id = body.get("id")

        if not method:
            raise HTTPException(
                status_code=400, detail="Missing method in JSON-RPC request"
            )

        # Route to appropriate handler
        try:
            if method == "initialize":
                result = {"capabilities": {"tools": {}, "resources": {}, "prompts": {}}}
            elif method == "resources/list":
                resources = await handle_list_resources()
                result = {"resources": [resource_to_dict(r) for r in resources]}
            elif method == "resources/read":
                uri = params.get("uri")
                if not uri:
                    raise ValueError("URI parameter is required for resources/read")
                from pydantic import AnyUrl

                content = await handle_read_resource(AnyUrl(uri))
                result = {"contents": [{"uri": uri, "text": content}]}
            elif method == "prompts/list":
                prompts = await handle_list_prompts()
                result = {"prompts": [prompt_to_dict(p) for p in prompts]}
            elif method == "prompts/get":
                name = params.get("name")
                arguments = params.get("arguments", {})
                if not name:
                    raise ValueError("Name parameter is required for prompts/get")
                prompt_result = await handle_get_prompt(name, arguments)
                result = {
                    "messages": [
                        {
                            "role": "user",
                            "content": {"type": "text", "text": msg.content.text},
                        }
                        for msg in prompt_result.messages
                    ]
                }
            elif method == "tools/list":
                tools = await handle_list_tools()
                result = {"tools": [tool_to_dict(t) for t in tools]}
            elif method == "tools/call":
                name = params.get("name")
                arguments = params.get("arguments", {})
                if not name:
                    raise ValueError("Name parameter is required for tools/call")
                tool_result = await handle_call_tool(name, arguments)
                result = {
                    "content": [
                        {"type": "text", "text": content.text}
                        for content in tool_result
                    ]
                }
            else:
                raise HTTPException(status_code=404, detail=f"Unknown method: {method}")

        except HTTPException as e:
            # Re-raise HTTPException to be handled by FastAPI
            raise e
        except Exception as e:
            logger.error(f"Error handling MCP method {method}: {e}")
            return JSONResponse(
                status_code=500,
                content={
                    "jsonrpc": "2.0",
                    "error": {"code": -32000, "message": str(e)},
                    "id": request_id,
                },
            )

        # Return JSON-RPC response
        return JSONResponse({"jsonrpc": "2.0", "result": result, "id": request_id})

    except HTTPException as e:
        # Re-raise HTTPException to be handled by FastAPI with correct status code
        raise e
    except Exception as e:
        logger.error(f"Unexpected error in MCP endpoint: {e}")
        return JSONResponse(
            status_code=400,
            content={
                "jsonrpc": "2.0",
                "error": {"code": -32700, "message": "Parse error"},
                "id": None,
            },
        )


@app.get("/mcp/stream")
async def mcp_stream_endpoint(request: Request):
    """Enhanced Server-Sent Events endpoint with connection management and resource cleanup."""

    # Generate unique connection ID
    import uuid

    connection_id = str(uuid.uuid4())

    # Check if we can add a new connection
    if not sse_manager.add_connection(connection_id):
        raise HTTPException(status_code=503, detail="Maximum SSE connections reached")

    async def event_generator():
        try:
            # Send initial connection event
            initial_event = {
                "type": "connection",
                "status": "connected",
                "timestamp": time.time(),
                "connection_id": connection_id,
                "active_connections": sse_manager.get_connection_count(),
            }
            yield f"data: {json.dumps(initial_event)}\n\n"

            # Send periodic heartbeat with connection management
            heartbeat_count = 0
            max_heartbeats = 720  # Maximum 6 hours (720 * 30 seconds)

            while heartbeat_count < max_heartbeats:
                await asyncio.sleep(30)  # Send heartbeat every 30 seconds

                # Check if connection is still valid
                if not sse_manager.is_connection_active(connection_id):
                    logger.info(
                        f"SSE connection {connection_id} no longer tracked, terminating"
                    )
                    break

                heartbeat = {
                    "type": "heartbeat",
                    "timestamp": time.time(),
                    "connection_id": connection_id,
                    "heartbeat_count": heartbeat_count,
                    "server_info": {
                        "uptime": time.time() - metrics["start_time"],
                        "requests_total": metrics["requests_total"],
                        "active_sse_connections": sse_manager.get_connection_count(),
                    },
                }
                yield f"data: {json.dumps(heartbeat)}\n\n"
                heartbeat_count += 1

            # Send connection timeout event
            if heartbeat_count >= max_heartbeats:
                timeout_event = {
                    "type": "timeout",
                    "message": "Connection timeout after maximum heartbeats",
                    "timestamp": time.time(),
                    "connection_id": connection_id,
                }
                yield f"data: {json.dumps(timeout_event)}\n\n"

        except asyncio.CancelledError:
            logger.info(f"SSE connection {connection_id} cancelled")
            disconnect_event = {
                "type": "disconnection",
                "reason": "cancelled",
                "timestamp": time.time(),
                "connection_id": connection_id,
            }
            yield f"data: {json.dumps(disconnect_event)}\n\n"
        except Exception as e:
            logger.error(f"Error in SSE stream {connection_id}: {e}")
            error_event = {
                "type": "error",
                "message": str(e),
                "timestamp": time.time(),
                "connection_id": connection_id,
            }
            yield f"data: {json.dumps(error_event)}\n\n"
        finally:
            # Always cleanup connection on exit
            sse_manager.remove_connection(connection_id)
            logger.info(f"SSE connection {connection_id} cleaned up")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable Nginx buffering
            "X-Connection-ID": connection_id,
        },
    )


@app.get("/")
async def root():
    """Root endpoint with server information."""
    uptime = time.time() - metrics["start_time"]

    return JSONResponse(
        {
            "name": "Datetime MCP Server",
            "version": "0.1.0",
            "transport": "http",
            "server": "hypercorn",
            "uptime_seconds": uptime,
            "endpoints": {
                "health": "/health",
                "metrics": "/metrics",
                "mcp": "/mcp",
                "stream": "/mcp/stream",
                "docs": "/docs",
            },
            "features": [
                "HTTP/2 support",
                "Multi-threading",
                "uvloop optimization",
                "Real-time metrics",
                "Server-Sent Events",
            ],
        }
    )


def create_hypercorn_config(
    host: str = "0.0.0.0",
    port: int = 8000,
    workers: int = None,
    log_level: str = "info",
    reload: bool = False,
) -> Config:
    """Create optimized Hypercorn configuration."""
    config = Config()

    # Basic settings
    config.bind = [f"{host}:{port}"]
    config.log_level = log_level.upper()

    # Performance optimizations
    config.worker_class = "trio"  # Use trio for better async performance
    config.workers = workers or max(
        1, (os.cpu_count() or 1) // 2
    )  # Conservative worker count
    config.threads = 2  # Enable threading support
    config.max_requests = 1000  # Restart workers after handling 1000 requests
    config.max_requests_jitter = 100  # Add jitter to max_requests

    # HTTP/2 and HTTP/3 support
    config.protocols = ["h2", "http/1.1"]  # Enable HTTP/2

    # Connection settings
    config.keep_alive_timeout = 65
    config.graceful_timeout = 30
    config.max_incomplete_event_size = 16384

    # SSL/TLS (can be configured later)
    # config.certfile = "path/to/cert.pem"
    # config.keyfile = "path/to/key.pem"

    # Development settings
    if reload:
        config.use_reloader = True
        config.reload_includes = ["*.py"]

    # Logging
    config.access_log_format = (
        '[%(asctime)s] %(h)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'
    )

    return config


async def shutdown_handler(server_task):
    """Graceful shutdown handler."""
    logger.info("Shutting down HTTP server...")
    server_task.cancel()
    try:
        await server_task
    except asyncio.CancelledError:
        pass
    logger.info("HTTP server shutdown complete")


def run_http_server(
    host: str = "0.0.0.0",
    port: int = 8000,
    workers: int = None,
    reload: bool = False,
    log_level: str = "info",
):
    """Run the HTTP server using Hypercorn with optimal performance settings."""
    logger.info(f"Starting Datetime MCP HTTP server on {host}:{port}")
    logger.info(
        f"Workers: {workers or 'auto'}, Reload: {reload}, Log level: {log_level}"
    )

    # Create configuration
    config = create_hypercorn_config(host, port, workers, log_level, reload)

    async def main():
        # Setup signal handlers for graceful shutdown
        server_task = None

        def signal_handler(sig, frame):
            if server_task:
                asyncio.create_task(shutdown_handler(server_task))

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        try:
            # Start the server
            server_task = asyncio.create_task(serve(app, config))
            await server_task
        except asyncio.CancelledError:
            logger.info("Server cancelled")
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        except Exception as e:
            logger.error(f"Server error: {e}")
            raise

    # Run with the optimal event loop
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_http_server()
