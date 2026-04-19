"""
Structured logging setup for the Failure-First Planner.
Call configure_logging() once at application startup (in run.py).
"""
import logging
import sys
from src.utils.config import Config


def configure_logging() -> None:
    """Configure root logger with a clean, readable format."""
    level = getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO)

    fmt = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"
    date_fmt = "%H:%M:%S"

    handler = logging.StreamHandler(open(sys.stdout.fileno(), mode="w", encoding="utf-8", closefd=False))
    handler.setFormatter(logging.Formatter(fmt, datefmt=date_fmt))

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)

    # Quiet noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("geopy").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
