import queue
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler, QueueHandler, QueueListener


def _prepare_log_file_path(project_root, folder_name, log_file_name):
    """Creates the parent directory for a log file relative to the project root.

    Args:
        project_root (Path): The absolute path to the root directory of the project.
        folder_name (str): The name of the target directory for log files.
        log_file_name (str): The filename of the log.

    Returns:
        Path: A Path object pointing to the absolute location of the log file.
    """
    path = Path(folder_name) / log_file_name

    if not path.is_absolute():
        path = project_root / path

    absolute_path = path.resolve()
    absolute_path.parent.mkdir(parents=True, exist_ok=True)

    return absolute_path


def _setup_file_handler(file_path):
    """Configures and returns a rolling file handler.

    Args:
        file_path (Path): Absolute path where the log file should be saved.

    Returns:
        RotatingFileHandler: An initialized file handler.
    """
    file_handler = RotatingFileHandler(
        filename=file_path,
        maxBytes=500000,
        backupCount=3,
        encoding="utf-8"
    )
    return file_handler


def _setup_log_listener(console_handler, file_handler, log_level):
    """Configures the log listener with non-blocking queue handlers.

    Args:
        console_handler (logging.StreamHandler): Output stream handler for the terminal.
        file_handler (RotatingFileHandler): Rolling file handler for disk storage.
        log_level (str): The logging level to apply globally.

    Returns:
        QueueListener: The globally configured queue log listener.
    """
    log_formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(log_formatter)
    file_handler.setFormatter(log_formatter)

    console_handler.setLevel(log_level)
    file_handler.setLevel(log_level)

    log_queue = queue.Queue()
    queue_handler = QueueHandler(log_queue)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(queue_handler)

    logging.getLogger("telegram").setLevel(logging.CRITICAL)
    logging.getLogger("httpx").setLevel(logging.CRITICAL)

    listener = QueueListener(log_queue, console_handler, file_handler, respect_handler_level=True)
    return listener


def init_app_logging(project_root, folder_name="logs", log_file_name="tg_bot.log", log_level="INFO"):
    """Initializes non-blocking application logging with console and file handlers.

    Args:
        project_root (Path): The absolute path to the root directory of the project.
        folder_name (str): Target directory for log files. Created if it doesn't exist.
            Defaults to 'logs'.
        log_file_name (str): Name of the log file. Defaults to 'tg_bot.log'.
        log_level (str): Target logging level. Defaults to 'INFO'.

    Returns:
        QueueListener: Configured queue log listener.
    """
    file_path = _prepare_log_file_path(project_root=project_root, folder_name=folder_name, log_file_name=log_file_name)
    console_handler = logging.StreamHandler()
    file_handler = _setup_file_handler(file_path=file_path)
    listener = _setup_log_listener(console_handler=console_handler, file_handler=file_handler, log_level=log_level)
    listener.start()
    return listener


def stop_app_logging(listener):
    """Gracefully stops the log listener and flushes the queue.

    Args:
        listener (QueueListener): The active log listener instance to stop.

    Returns:
        None: This function does not return a value.
    """
    if listener:
        try:
            listener.stop()
        except Exception:
            pass
