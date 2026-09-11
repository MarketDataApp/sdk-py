from logging import Formatter, Logger, StreamHandler, getLogger

from marketdata.settings import settings


def get_logger() -> Logger:
    """The SDK's logger, with one stream handler for the whole process.

    Every client built without a ``logger=`` asks for it. The handler is added
    only when the logger has none: one per call wrote every record once per
    client built (#104), and a handler the caller attached to
    ``marketdata.logger`` before building a client stands in for it. The
    handler has no level of its own, so the logger's level, set here from the
    settings, decides.
    """
    logger = getLogger(__name__)
    logger.setLevel(settings.marketdata_logging_level)

    if not logger.handlers:
        handler = StreamHandler()
        handler.setFormatter(
            Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        logger.addHandler(handler)
    return logger
