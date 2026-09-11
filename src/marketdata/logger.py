import sys
import threading
from logging import Formatter, Handler, Logger, StreamHandler, getLogger

from marketdata.settings import settings

_lock = threading.Lock()


class _StderrHandler(StreamHandler):
    """A stream handler that writes to whatever ``sys.stderr`` is when a
    record is emitted, as the standard library's last-resort handler does.

    One handler now serves the whole process (#104), so it cannot keep the
    stream of the moment it was built: had the first client been built while
    stderr was redirected (``contextlib.redirect_stderr``, a captured test),
    every later line would have gone to that stream.
    """

    def __init__(self) -> None:
        Handler.__init__(self)

    @property
    def stream(self):
        return sys.stderr


def get_logger() -> Logger:
    """The SDK's logger, with one stream handler for the whole process.

    Every client built without a ``logger=`` asks for it. The handler is added
    once, and only when the logger has none: a handler per call wrote every
    record once per client built (#104), and a handler the caller attached to
    ``marketdata.logger`` before building a client stands in for it. The
    logger and the SDK's handler take their level from the settings on every
    call, as each new handler used to.
    """
    level = settings.marketdata_logging_level
    logger = getLogger(__name__)
    with _lock:
        logger.setLevel(level)
        if not logger.handlers:
            handler = _StderrHandler()
            handler.setFormatter(
                Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            )
            logger.addHandler(handler)
        for handler in logger.handlers:
            if isinstance(handler, _StderrHandler):
                handler.setLevel(level)
    return logger
