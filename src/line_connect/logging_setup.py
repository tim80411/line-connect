"""structlog configuration: JSON in production, pretty console for dev."""

import logging

import structlog


def setup_logging(level: str, fmt: str) -> None:
    log_level = logging.getLevelNamesMapping().get(level.upper(), logging.INFO)

    renderer: structlog.typing.Processor
    if fmt == "console":
        renderer = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        cache_logger_on_first_use=True,
    )

    # Route stdlib logging (uvicorn, httpx) through the same level.
    logging.basicConfig(level=log_level, format="%(levelname)s %(name)s %(message)s")
