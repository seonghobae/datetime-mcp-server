"""
Logging configuration for the datetime MCP server.

Provides structured logging with different levels, formatters, and handlers
for better debugging and monitoring capabilities.
"""

import logging
import logging.handlers
import sys
import json
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter that outputs structured JSON logs for better parsing
    and analysis in production environments.
    """
    
    def __init__(self, include_timestamp: bool = True):
        super().__init__()
        self.include_timestamp = include_timestamp
    
    def format(self, record: logging.LogRecord) -> str:
        # Create the base log entry
        log_entry = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        if self.include_timestamp:
            log_entry["timestamp"] = datetime.utcnow().isoformat() + "Z"
        
        # Add exception information if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info)
            }
        
        # Add extra fields if present
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                          'filename', 'module', 'lineno', 'funcName', 'created', 'msecs', 
                          'relativeCreated', 'thread', 'threadName', 'processName', 
                          'process', 'getMessage', 'exc_info', 'exc_text', 'stack_info']:
                extra_fields[key] = value
        
        if extra_fields:
            log_entry["extra"] = extra_fields
        
        # Add source information
        log_entry["source"] = {
            "file": record.filename,
            "line": record.lineno,
            "function": record.funcName
        }
        
        return json.dumps(log_entry, separators=(',', ':'))


class ServerHealthLogger:
    """
    Specialized logger for server health metrics and monitoring.
    """
    
    def __init__(self, logger_name: str = "datetime_mcp_server.health"):
        self.logger = logging.getLogger(logger_name)
    
    def log_startup(self, transport_mode: str, config: Dict[str, Any] = None):
        """Log server startup event"""
        self.logger.info(
            "Server starting up",
            extra={
                "event": "server_startup",
                "transport_mode": transport_mode,
                "config": config or {}
            }
        )
    
    def log_shutdown(self, reason: str = "normal", exit_code: int = 0):
        """Log server shutdown event"""
        self.logger.info(
            "Server shutting down",
            extra={
                "event": "server_shutdown", 
                "reason": reason,
                "exit_code": exit_code
            }
        )
    
    def log_request(self, method: str, params: Optional[Dict] = None, 
                   processing_time_ms: Optional[float] = None, success: bool = True):
        """Log MCP request processing"""
        self.logger.info(
            f"MCP request processed: {method}",
            extra={
                "event": "mcp_request",
                "method": method,
                "params": params,
                "processing_time_ms": processing_time_ms,
                "success": success
            }
        )
    
    def log_error(self, error: Exception, context: str = "unknown"):
        """Log server errors with context"""
        self.logger.error(
            f"Server error in {context}: {str(error)}",
            extra={
                "event": "server_error",
                "error_type": type(error).__name__,
                "context": context
            },
            exc_info=True
        )
    
    def log_memory_usage(self, memory_mb: float, note_count: int = 0):
        """Log memory usage metrics"""
        self.logger.info(
            f"Memory usage: {memory_mb:.1f}MB",
            extra={
                "event": "memory_usage",
                "memory_mb": memory_mb,
                "note_count": note_count
            }
        )


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    structured: bool = False,
    max_file_size_mb: int = 10,
    backup_count: int = 5
) -> logging.Logger:
    """
    Set up logging configuration for the datetime MCP server.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (if None, logs only to console)
        structured: Whether to use structured JSON logging
        max_file_size_mb: Maximum log file size in MB before rotation
        backup_count: Number of backup log files to keep
    
    Returns:
        logging.Logger: Configured root logger
    """
    # Clear any existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Set logging level
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)
    
    # Create formatter
    if structured:
        formatter = StructuredFormatter()
    else:
        formatter = logging.Formatter(
            fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(numeric_level)
    root_logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        # Ensure log directory exists
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Use rotating file handler to prevent huge log files
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_file_size_mb * 1024 * 1024,
            backupCount=backup_count
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(numeric_level)
        root_logger.addHandler(file_handler)
    
    # Set specific logger levels for noisy libraries
    logging.getLogger('mcp').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    # Create main server logger
    server_logger = logging.getLogger("datetime_mcp_server")
    server_logger.info(f"Logging initialized at level {level}")
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(f"datetime_mcp_server.{name}")


def log_function_call(logger: logging.Logger):
    """
    Decorator to log function calls with parameters and execution time.
    Useful for debugging and performance monitoring.
    """
    def decorator(func):
        import functools
        import time
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            
            # Log function entry
            logger.debug(
                f"Calling {func.__name__}",
                extra={
                    "event": "function_call",
                    "function": func.__name__,
                    "args_count": len(args),
                    "kwargs": list(kwargs.keys())
                }
            )
            
            try:
                result = await func(*args, **kwargs)
                execution_time = (time.time() - start_time) * 1000
                
                # Log successful completion
                logger.debug(
                    f"Completed {func.__name__} in {execution_time:.2f}ms",
                    extra={
                        "event": "function_completed",
                        "function": func.__name__,
                        "execution_time_ms": execution_time,
                        "success": True
                    }
                )
                
                return result
                
            except Exception as e:
                execution_time = (time.time() - start_time) * 1000
                
                # Log error
                logger.error(
                    f"Error in {func.__name__} after {execution_time:.2f}ms: {str(e)}",
                    extra={
                        "event": "function_error",
                        "function": func.__name__,
                        "execution_time_ms": execution_time,
                        "error_type": type(e).__name__,
                        "success": False
                    },
                    exc_info=True
                )
                
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            
            # Log function entry
            logger.debug(
                f"Calling {func.__name__}",
                extra={
                    "event": "function_call",
                    "function": func.__name__,
                    "args_count": len(args),
                    "kwargs": list(kwargs.keys())
                }
            )
            
            try:
                result = func(*args, **kwargs)
                execution_time = (time.time() - start_time) * 1000
                
                # Log successful completion
                logger.debug(
                    f"Completed {func.__name__} in {execution_time:.2f}ms",
                    extra={
                        "event": "function_completed",
                        "function": func.__name__,
                        "execution_time_ms": execution_time,
                        "success": True
                    }
                )
                
                return result
                
            except Exception as e:
                execution_time = (time.time() - start_time) * 1000
                
                # Log error
                logger.error(
                    f"Error in {func.__name__} after {execution_time:.2f}ms: {str(e)}",
                    extra={
                        "event": "function_error",
                        "function": func.__name__,
                        "execution_time_ms": execution_time,
                        "error_type": type(e).__name__,
                        "success": False
                    },
                    exc_info=True
                )
                
                raise
        
        # Return appropriate wrapper based on whether function is async
        import asyncio
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator 