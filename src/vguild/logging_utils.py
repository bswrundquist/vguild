"""Logging configuration for vguild."""

from __future__ import annotations

import logging

from rich.console import Console
from rich.logging import RichHandler

console = Console()
_err_console = Console(stderr=True)


def setup_logging(verbose: bool = False) -> None:
    """Configure root logger with Rich formatting."""
    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=_err_console, rich_tracebacks=True, markup=True)],
    )

    # Suppress noisy third-party loggers
    for noisy in ("httpx", "httpcore", "anthropic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
