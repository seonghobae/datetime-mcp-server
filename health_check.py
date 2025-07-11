#!/usr/bin/env python3
"""Simple health check script for Docker container."""

import sys


def health_check():
    """Basic health check - verify Python can import our module."""
    try:
        # Add src directory to Python path
        sys.path.insert(0, "/app/src")

        # Test that we can import the main module
        import datetime_mcp_server  # noqa: F401

        print("Health check passed: Module imports successfully")
        return 0
    except ImportError as e:
        print(f"Health check failed: {e}")
        return 1
    except Exception as e:
        print(f"Health check failed with unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(health_check())
