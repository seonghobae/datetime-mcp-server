"""Main entry point for the datetime MCP server with transport selection."""

import argparse
import asyncio
import os
import sys

from .server import main as stdio_main
from .http_server import run_http_server


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Datetime MCP Server - Precise date/time calculations for LLMs"
    )

    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default=os.getenv("TRANSPORT_MODE", "stdio"),
        help="Transport mode: stdio for standard I/O, http for HTTP server (default: stdio)",
    )

    # HTTP-specific arguments
    parser.add_argument(
        "--host",
        default=os.getenv("HTTP_HOST", "0.0.0.0"),
        help="HTTP server host (default: 0.0.0.0)",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("HTTP_PORT", "8000")),
        help="HTTP server port (default: 8000)",
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=int(os.getenv("HTTP_WORKERS", "1")),
        help="Number of HTTP workers (default: 1)",
    )

    parser.add_argument(
        "--reload",
        action="store_true",
        default=os.getenv("HTTP_RELOAD", "false").lower() == "true",
        help="Enable auto-reload for development",
    )

    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error"],
        default=os.getenv("LOG_LEVEL", "info"),
        help="Log level (default: info)",
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    if args.transport == "stdio":
        print("Starting Datetime MCP Server in STDIO mode...", file=sys.stderr)
        asyncio.run(stdio_main())
    elif args.transport == "http":
        print(
            f"Starting Datetime MCP Server in HTTP mode on {args.host}:{args.port}...",
            file=sys.stderr,
        )
        run_http_server(
            host=args.host,
            port=args.port,
            workers=args.workers,
            reload=args.reload,
            log_level=args.log_level,
        )
    else:
        print(f"Unknown transport mode: {args.transport}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
