import logging
from pathlib import Path
from logging import StreamHandler, Logger
from logging.handlers import RotatingFileHandler


def create_log_file_path(folder_name: str, log_file: str) -> Path:
    """Creates log folder if it doesn't exist."""
    folder = Path(folder_name)
    folder.mkdir(parents=True, exist_ok=True)
    return folder / log_file


def setup_file_handler(file_path: Path) -> RotatingFileHandler:
    """Configures file error handler."""
    file_handler = RotatingFileHandler(
        filename=file_path,
        maxBytes=500000,
        backupCount=2,
        encoding="utf-8"
    )
    return file_handler


def setup_root_logger(console_handler: StreamHandler, file_handler: RotatingFileHandler) -> Logger:
    """Configures the root error logger."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[console_handler, file_handler]
    )

    logging.getLogger("telegram.ext.updater").setLevel(logging.CRITICAL)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.CRITICAL)

    return logging.getLogger()


def init_app_logging(folder_name: str, log_file: str) -> Logger:
    """Initializes application logging with console and file handlers.

    Args:
        folder_name: Target directory for log files. Created if it doesn't exist.
        log_file: Name of the log file.

    Returns:
        Configured root logger.
    """
    file_path = create_log_file_path(folder_name, log_file)
    console_handler = logging.StreamHandler()
    file_handler = setup_file_handler(file_path)
    logger = setup_root_logger(console_handler, file_handler)
    return logger
