import sys
from logging import Formatter, Handler, Logger, StreamHandler, getLogger

from marketdata.settings import settings


class _StderrHandler(StreamHandler):
    """A stream handler that writes to whatever ``sys.stderr`` is when a
    record is emitted, as the standard library's last-resort handler does,
    unless a stream was set on it (``setStream``, or an assignment).

    One handler serves the whole process (#104), so it cannot keep the stream
    of the moment it was built: had the first client been built while stderr
    was redirected (``contextlib.redirect_stderr``, a captured test), every
    later line would have gone to that stream.
    """

    def __init__(self) -> None:
        Handler.__init__(self)
        self._stream = None

    @property
    def stream(self):
        return sys.stderr if self._stream is None else self._stream

    @stream.setter
    def stream(self, value) -> None:
        self._stream = value


# The one handler, attached on first use. `addHandler` ignores a handler the
# logger already has, and checks under the logging module's own lock, so two
# clients built at the same moment cannot attach two. That is why the SDK
# takes no lock of its own: one would have to be reset after a fork, and be
# taken in the same order as the logging module's.
_HANDLER = _StderrHandler()
_HANDLER.setFormatter(Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))


def get_logger() -> Logger:
    """The SDK's logger, with one stream handler for the whole process.

    Every client built without a ``logger=`` asks for it. The handler is
    attached only when the logger has none: a handler per call wrote every
    record once per client built (#104), and a handler the caller attached to
    ``marketdata.logger`` before building a client stands in for it. The
    logger and the SDK's handler take their level from the settings on every
    call, as each new handler used to.
    """
    level = settings.marketdata_logging_level
    logger = getLogger(__name__)
    logger.setLevel(level)
    _HANDLER.setLevel(level)
    if not logger.handlers:
        logger.addHandler(_HANDLER)
    return logger
