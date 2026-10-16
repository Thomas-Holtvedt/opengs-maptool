from __future__ import annotations
import sys
import logging
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
import platformdirs

from opengs_maptool import config
from opengs_maptool.simple_types import LoggerCategoryConfiguration, LoggingLevel


lowest_logging_level = LoggingLevel.NOTSET.logging_internal_value
console_logging_level = LoggingLevel.INFO.logging_internal_value

class CategoryLoggerRegistry:
    """Registry of configured category loggers. Keep this block easy to edit."""

    def __init__(self):
        self._loggers: dict[str, CategoryLogger] = {}
        self._initialize_from_config()

    def _initialize_from_config(self) -> None:
        """Build the category logger instances from config.LOG_CATEGORIES."""
        #############################################################################
        # UPDATE THIS WHEN NEW LOGGER CATEGORIES ARE ADDED TO config.LOG_CATEGORIES #
        #############################################################################
        self.task_progress = self.create_category_logger("task_progress", config.LOG_CATEGORIES["task_progress"])
        self.export = self.create_category_logger("export", config.LOG_CATEGORIES["export"])
        self.command = self.create_category_logger("command", config.LOG_CATEGORIES["command"])

    def create_category_logger(self, category_name: str, config_entry: LoggerCategoryConfiguration) -> CategoryLogger:
        """Create a new category logger at runtime."""
        new_logger = CategoryLogger(category_name, config_entry)
        self._loggers[category_name] = new_logger
        return new_logger

class CategoryLogger:
    """Logger for a specific category, with its own level and prefix."""

    def __init__(self, category_name: str, config_entry: LoggerCategoryConfiguration):
        self.category_name = category_name
        self.prefix = config_entry.prefix
        self.level = config_entry.level.logging_internal_value
        self.enabled = config_entry.enabled

        self.logger = logging.getLogger(f"opengs_maptool.{category_name}")
        self.logger.setLevel(self.level)
        self.logger.propagate = True
        self.logger.disabled = not self.enabled

    def send(self, message: str, *args, **kwargs):
        if not self.enabled:
            return
        formatted = f"{self.prefix} {message}" if self.prefix else message
        self.logger.log(self.level, formatted, *args, **kwargs)

class LoggingService:
    """Manages application logging with OS-independent paths and daily rotation."""

    def __init__(self):
        """Initialize the logging service (does not start logging yet)."""
        self._root_logger = logging.getLogger("opengs_maptool")
        self._log_dir = None
        self._log_file = None
        self.initialized = False
        self._category_logger_registry = CategoryLoggerRegistry()
        self.loggers = self._category_logger_registry

    def _print_meta_warning(self, message: str) -> None:
        """Print a warning message to the console."""
        print(f"[LoggingService] WARNING: {message}", file=sys.stderr)

    def _is_frozen(self) -> bool:
        """Return True when executed as a compiled executable."""
        return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')

    def _get_log_directory(self) -> Path:
        """Return the platform-appropriate log directory."""
        if self._is_frozen():
            base_dir = Path(platformdirs.user_data_dir(config.LOG_DIR_NAME))
        else:
            service_file = Path(__file__)
            project_root = service_file.parent.parent.parent
            base_dir = project_root

        return base_dir / 'logs'

    def _create_log_directory(self) -> bool:
        """Create the log directory if it does not exist."""
        try:
            self._log_dir.mkdir(parents=True, exist_ok=True)
            return True
        except OSError as error:
            self._print_meta_warning(f"Failed to create log directory '{self._log_dir}': {error}")
            return False

    def _get_log_filename(self) -> str:
        """Return the current daily log filename."""
        today = datetime.now().strftime('%Y-%m-%d')
        return f'app-{today}.log'

    def initialize(self) -> bool:
        """Initialize the logging service and attach handlers."""
        if self.initialized:
            return True

        self._log_dir = self._get_log_directory()
        if not self._create_log_directory():
            self._print_meta_warning("Logging to console only (could not create log directory)")
            self._setup_console_logging()
            self.initialized = True
            return False

        self._log_file = self._log_dir / self._get_log_filename()

        self._root_logger.setLevel(lowest_logging_level)
        self._root_logger.handlers.clear()

        formatter = logging.Formatter(
            config.LOG_FORMAT,
            datefmt=config.LOG_DATE_FORMAT,
        )

        try:
            file_handler = TimedRotatingFileHandler(
                filename=str(self._log_file),
                when='midnight',
                interval=1,
                backupCount=config.LOG_MAX_BACKUPS,
                encoding='utf-8',
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(lowest_logging_level)
            self._root_logger.addHandler(file_handler)
        except OSError as error:
            self._print_meta_warning(f"Failed to create file handler: {error}")
            self._setup_console_logging()
            self.initialized = True
            return False

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(console_logging_level)
        self._root_logger.addHandler(console_handler)

        self.initialized = True
        return True

    def _setup_console_logging(self) -> None:
        """Fallback to console-only logging if the directory cannot be created."""
        formatter = logging.Formatter(
            config.LOG_FORMAT,
            datefmt=config.LOG_DATE_FORMAT,
        )
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(console_logging_level)
        self._root_logger.addHandler(console_handler)
        self._root_logger.info("==== Console-only logging (fallback mode) ====")

LOGGING_SERVICE = LoggingService()
LOGGING_SERVICE.initialize()
