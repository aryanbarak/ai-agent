import logging
import sys
import json
from datetime import datetime
from typing import Any


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add request_id if available
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        
        # Add extra fields
        if hasattr(record, "extra"):
            log_data.update(record.extra)
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)


def setup_logger(name: str, level: str = "INFO") -> logging.Logger:
    """Setup a structured logger with JSON output"""
    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    logger.setLevel(getattr(logging, level.upper()))
    
    # Console handler with JSON formatter
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    
    logger.addHandler(handler)
    logger.propagate = False
    
    return logger


def log_with_context(
    logger: logging.Logger,
    level: str,
    message: str,
    request_id: str | None = None,
    **kwargs: Any
) -> None:
    """Log a message with additional context"""
    extra_data = kwargs.copy()
    
    if request_id:
        extra_data["request_id"] = request_id
    
    # Create a LogRecord with extra data
    if extra_data:
        logger.log(
            getattr(logging, level.upper()),
            message,
            extra={"extra": extra_data}
        )
    else:
        logger.log(getattr(logging, level.upper()), message)


# Create default loggers
api_logger = setup_logger("agent.api")
fiae_logger = setup_logger("agent.fiae")
cache_logger = setup_logger("agent.cache")
