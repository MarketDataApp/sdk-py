from logging import Formatter, Logger, StreamHandler, getLogger

from marketdata.settings import settings


def get_logger() -> Logger:
    logger = getLogger(__name__)
    logger.setLevel(settings.marketdata_logging_level)

    formatter = Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    handler = StreamHandler()
    handler.setLevel(settings.marketdata_logging_level)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger
