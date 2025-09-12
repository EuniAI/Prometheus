"""
Unified Log Manager - Improved Version

This module provides a centralized logging management solution for the entire Prometheus project.
All logger configuration and retrieval should be done through this module.
"""

import logging
import os
import sys
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from prometheus.configuration.config import settings


class ColoredFormatter(logging.Formatter):
    """Colored log formatter"""

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Purple
        "RESET": "\033[0m",  # Reset color
    }

    # Colored level names
    COLORED_LEVELNAMES = {
        "DEBUG": f"{COLORS['DEBUG']}DEBUG{COLORS['RESET']}",
        "INFO": f"{COLORS['INFO']}INFO{COLORS['RESET']}",
        "WARNING": f"{COLORS['WARNING']}WARNING{COLORS['RESET']}",
        "ERROR": f"{COLORS['ERROR']}ERROR{COLORS['RESET']}",
        "CRITICAL": f"{COLORS['CRITICAL']}CRITICAL{COLORS['RESET']}",
    }

    def __init__(self, fmt=None, datefmt=None, use_colors=True):
        """
        Initialize colored formatter

        Args:
            fmt: Log format string
            datefmt: Date format string
            use_colors: Whether to use colors
        """
        super().__init__(fmt, datefmt)
        self.use_colors = use_colors and self._supports_color()

    def _supports_color(self) -> bool:
        """Check if terminal supports colors"""
        # Check if running in a color-supporting terminal
        return (
            hasattr(sys.stdout, "isatty")
            and sys.stdout.isatty()
            and sys.platform != "win32"  # Windows may need special handling
        ) or "FORCE_COLOR" in os.environ

    def format(self, record):
        """Format log record"""
        if self.use_colors and record.levelname in self.COLORED_LEVELNAMES:
            # Save original level name
            original_levelname = record.levelname
            # Use colored level name
            record.levelname = self.COLORED_LEVELNAMES[record.levelname]

            # Format message
            formatted = super().format(record)

            # Restore original level name
            record.levelname = original_levelname

            return formatted
        else:
            return super().format(record)


class LoggerManager:
    """Logger manager class, responsible for creating and configuring all loggers"""

    _instance: Optional["LoggerManager"] = None
    _initialized: bool = False

    def __new__(cls) -> "LoggerManager":
        """Singleton pattern implementation"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize logger manager"""
        self.log_level = getattr(settings, "LOGGING_LEVEL")
        self.issue_log_dir = Path(getattr(settings, "WORKING_DIRECTORY")) / "answer_issue_logs"
        if not self._initialized:
            # Use Local storage to manage thread sessions
            self.thread_sessions: Dict[int, str] = {}
            self.session_lock = threading.Lock()

            self._setup_root_logger()
            self._initialized = True

    def _setup_root_logger(self):
        """Setup root logger"""
        # Get root logger
        self.root_logger = logging.getLogger("prometheus")

        # Clear existing handlers to avoid duplication
        self.root_logger.handlers.clear()

        # Set log level
        self.root_logger.setLevel(getattr(logging, self.log_level))

        # Create colored formatter for console output
        self.colored_formatter = ColoredFormatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        # Create plain formatter for file output
        self.file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        # Create console handler (using colored formatter)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(self.colored_formatter)
        console_handler.setLevel(
            getattr(logging, self.log_level)
        )  # Ensure console handler uses same level
        self.root_logger.addHandler(console_handler)

        # Prevent log propagation to parent logger
        self.root_logger.propagate = False

        # Log configuration information
        self._log_configuration()

    def _get_or_create_session_id(self, thread_id: int) -> str:
        """
        Get or create a unique session ID for the given thread ID.

        Args:
            thread_id: Thread ID

        Returns:
            Unique session ID string
        """
        with self.session_lock:
            if thread_id not in self.thread_sessions:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                unique_id = str(uuid.uuid4())[:8]
                self.thread_sessions[thread_id] = f"{timestamp}_{unique_id}"
            return self.thread_sessions[thread_id]

    def clear_thread_session(self, thread_id: int):
        """
        Clear the session ID for the given thread ID.

        Args:
            thread_id: Thread ID
        """
        with self.session_lock:
            if thread_id in self.thread_sessions:
                del self.thread_sessions[thread_id]

    def _set_multi_threads_log_file_handler(
        self, thread_id: int, logger_name: str, force_new_file: bool = False
    ):
        """Set multi threads log file handler"""
        # Find existing log file for this thread_id, or create new one if none exists
        log_file_path = self._find_or_create_log_file(thread_id, force_new_file)
        file_handler = self.create_file_handler(log_file_path, logger_name)
        return file_handler

    def _find_or_create_log_file(self, thread_id: int, force_new_file: bool = False) -> Path:
        """
        Find existing log file for the thread_id, or create new one if none exists

        Args:
            thread_id: Thread ID to find/create log file for
            force_new_file: If True, always create a new file with timestamp, even if existing files exist

        Returns:
            Path to the log file (existing earliest one or newly created)
        """

        if force_new_file:
            self.clear_thread_session(thread_id)

        session_id = self._get_or_create_session_id(thread_id)
        log_file_path = self.issue_log_dir / f"{session_id}_{thread_id}.log"

        return log_file_path

    def _log_configuration(self):
        """Log configuration information"""
        # Dynamically get all attributes from settings
        config_attrs = [
            attr for attr in dir(settings) if attr.isupper() and not attr.startswith("_")
        ]

        for attr in config_attrs:
            value = getattr(settings, attr, "Not Set")

            # Check if the attribute name indicates a sensitive configuration
            is_sensitive = any(
                keyword in attr.upper() for keyword in ["KEY", "API", "PASSWORD", "SECRET"]
            )

            # If sensitive, mask the value
            if is_sensitive and value and value != "Not Set":
                masked_value = "*" * min(len(str(value)), 8)
                self.root_logger.info(f"{attr}={masked_value}")
            else:
                self.root_logger.info(f"{attr}={value}")

    def get_logger(self, name: str) -> logging.Logger:
        """
        Get logger with specified name

        Args:
            name: Logger name, recommended to use full module path

        Returns:
            Configured logger instance
        """
        logger = logging.getLogger(name)

        # If it's a child logger, inherit root logger configuration
        if name != "prometheus":
            logger.parent = self.root_logger
            logger.propagate = True

        return logger

    def create_file_handler(self, log_file_path: Path, logger_name: str) -> logging.FileHandler:
        """
        Create file handler for specified logger

        Args:
            log_file_path: Log file path
            logger_name: Logger name

        Returns:
            Configured file handler
        """
        # Ensure log directory exists
        log_file_path.parent.mkdir(parents=True, exist_ok=True)

        # Create file handler with append mode to preserve existing content
        file_handler = logging.FileHandler(log_file_path, mode="a")
        file_handler.setLevel(getattr(logging, self.log_level))
        file_handler.setFormatter(self.file_formatter)

        logger = logging.getLogger(logger_name)

        # If it's a child logger, inherit root logger configuration
        if logger_name != "prometheus":
            logger.parent = self.root_logger
            logger.propagate = True

        # Check if this logger already has a file handler to avoid duplicates
        has_file_handler = any(isinstance(h, logging.FileHandler) for h in logger.handlers)
        if not has_file_handler:
            logger.addHandler(file_handler)

        return file_handler

    def remove_file_handler(self, handler: logging.FileHandler, logger_name: str = "prometheus"):
        """
        Remove file handler

        Args:
            handler: Handler to remove
            logger_name: Logger name
        """
        logger = self.get_logger(logger_name)
        logger.removeHandler(handler)
        handler.close()

    def remove_multi_thread_file_handler(
        self, handler: logging.FileHandler, logger_name: str = None
    ):
        """
        Remove multi-thread file handler from specific logger

        Args:
            handler: File handler to remove
            logger_name: Logger name to remove handler from
        """
        if logger_name:
            logger = self.get_logger(logger_name)
            logger.removeHandler(handler)
        else:
            # Fallback: try to remove from root logger
            self.root_logger.removeHandler(handler)
        handler.close()


# Create global logger manager instance
logger_manager = LoggerManager()


def get_logger(name: str) -> logging.Logger:
    """
    Convenience function to get logger

    Args:
        name: Logger name, recommended to use __name__ or module path

    Returns:
        Configured logger instance

    Examples:
        >>> logger = get_logger(__name__)
        >>> logger = get_logger("prometheus.tools.web_search")
    """
    return logger_manager.get_logger(name)


def remove_multi_threads_log_file_handler(handler: logging.FileHandler, logger_name: str = None):
    """
    Convenience function to remove multi-thread file handler

    Args:
        handler: File handler to remove
        logger_name: Logger name (optional)
    """
    logger_manager.remove_multi_thread_file_handler(handler, logger_name)


def get_thread_logger(
    module_name: str, force_new_file: bool = False
) -> tuple[logging.Logger, logging.FileHandler]:
    """
    Convenience function to create a thread-specific logger with file handler in one call

    Args:
        module_name: Module name (usually __name__), if None, uses current module
        force_new_file: If True, always create a new log file with timestamp, even if existing files exist

    Returns:
        Tuple of (logger, file_handler) for easy cleanup

    Examples:
        >>> logger, file_handler = get_thread_logger(__name__)
        >>> logger.info("This goes to both console and file")
        >>> # In finally block:
        >>> remove_multi_threads_log_file_handler(file_handler, logger.name)

        >>> # Force creating a new file each time
        >>> logger, file_handler = get_thread_logger(__name__, force_new_file=True)
    """
    import threading

    # Get thread ID
    thread_id = threading.get_ident()
    logger_name = f"thread-{thread_id}.{module_name}"

    # Create file handler and logger
    file_handler = logger_manager._set_multi_threads_log_file_handler(
        thread_id, logger_name, force_new_file
    )
    logger = get_logger(logger_name)
    return logger, file_handler


def clear_current_thread_session():
    """
    Clear the current thread's session to ensure next log file is new

    Examples:
        >>> logger, file_handler = get_thread_logger(__name__)
        >>> try:
        >>>     # Do some work
        >>>     logger.info("Processing...")
        >>> finally:
        >>>     remove_multi_threads_log_file_handler(file_handler, logger.name)
        >>>     clear_current_thread_session()  # Clear session for next time
    """
    import threading

    thread_id = threading.get_ident()
    logger_manager.clear_thread_session(thread_id)
