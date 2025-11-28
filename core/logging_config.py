
"""
Centralized logging configuration for the Brain-Heart Agent API
Provides file-based logging with rotation and console output
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(log_dir: str = "logs", log_file: str = "api.log", 
                  max_bytes: int = 10_000_000, backup_count: int = 5,
                  log_level: int = logging.INFO):
    """
    Configure logging for the application with file rotation and console output.
    
    Args:
        log_dir: Directory to store log files (default: 'logs')
        log_file: Name of the log file (default: 'api.log')
        max_bytes: Maximum size of each log file before rotation (default: 10MB)
        backup_count: Number of backup files to keep (default: 5)
        log_level: Logging level (default: logging.INFO)
    
    Features:
        - Logs to both file and console (terminal)
        - Automatic log rotation when file size exceeds max_bytes
        - Keeps backup_count number of old log files
        - UTF-8 encoding for emoji and special character support
        - Captures all logs including raw thinking processes
    """
    
    # Create logs directory if it doesn't exist
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # Full path to log file
    log_file_path = log_path / log_file
    
    # Define log format - same as what you see in terminal
    log_format = '%(asctime)s %(name)s %(levelname)s: %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    # Create formatter
    formatter = logging.Formatter(log_format, datefmt=date_format)
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove any existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
    # Console Handler (StreamHandler) - for terminal output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File Handler (RotatingFileHandler) - for persistent logs with rotation
    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'  # Support for emojis and special characters
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Log initial setup message
    root_logger.info("=" * 80)
    root_logger.info(f"🚀 Logging system initialized")
    root_logger.info(f"📁 Log file: {log_file_path.absolute()}")
    root_logger.info(f"📊 Max file size: {max_bytes / 1_000_000:.1f} MB")
    root_logger.info(f"💾 Backup files: {backup_count}")
    root_logger.info(f"📝 Log level: {logging.getLevelName(log_level)}")
    root_logger.info("=" * 80)
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.
    
    Args:
        name: Name of the logger (usually __name__)
    
    Returns:
        Logger instance
    """
    return logging.getLogger(name)

