import sys
from logging import NOTSET, Formatter, Handler, Logger, StreamHandler, getLogger

from marketdata.settings import settings


class _StderrHandler(StreamHandler):
    """Stream handler that writes to the current ``sys.stderr`` unless a stream
    is set on it."""

    def __init__(self) -> None:
        Handler.__init__(self)
        self._stream = None

    @property
    def stream(self):
        return sys.stderr if self._stream is None else self._stream

    @stream.setter
    def stream(self, value) -> None:
        self._stream = value

    def setStream(self, stream):
        """Set the stream to write to, under the handler's lock.

        Returns the stream replaced, or ``None`` when ``stream`` is already the
        one set. ``None`` makes the handler follow the current ``sys.stderr``.
        """
        self.acquire()
        try:
            if stream is self._stream:
                return None
            result = self.stream
            # The handler's lock is reentrant, so `flush` can take it again here.
            self.flush()
            self.stream = stream
        finally:
            self.release()
        return result


_HANDLER = _StderrHandler()
_HANDLER.setFormatter(Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

# The level `get_logger` last applied; any other level was set elsewhere and is kept.
_applied_level = NOTSET


def get_logger() -> Logger:
    """Return the SDK's logger, ``marketdata.logger``.

    Attaches the shared stderr handler when the logger has none. The handler's
    level follows the settings on every call, and so does the logger's unless
    another level was set on it.
    """
    global _applied_level
    level = settings.marketdata_logging_level
    logger = getLogger(__name__)
    if logger.level in (NOTSET, _applied_level):
        logger.setLevel(level)
        _applied_level = logger.level
    _HANDLER.setLevel(level)
    if not logger.handlers:
        logger.addHandler(_HANDLER)
    return logger
