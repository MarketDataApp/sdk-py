import sys
from logging import NOTSET, Formatter, Handler, Logger, StreamHandler, getLogger

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

    def setStream(self, stream):
        """Set the stream to write to, and return the one written to before.

        The standard library skips the change when ``stream is self.stream``,
        and ``self.stream`` answers the live ``sys.stderr`` while none is set,
        so ``setStream(sys.stderr)`` did nothing and the handler went on
        following every redirection (#108 review). The comparison here is with
        the stream that was set. ``None`` goes back to the live ``sys.stderr``,
        and is also the way back after ``old = handler.setStream(stream)``:
        setting ``old`` again pins the stderr of that moment.
        """
        if stream is self._stream:
            return None
        result = self.stream
        self.acquire()
        try:
            self.flush()
            self.stream = stream
        finally:
            self.release()
        return result


# The one handler, attached on first use. `addHandler` ignores a handler the
# logger already has, and checks under the logging module's own lock, so two
# clients built at the same moment cannot attach two. That is why the SDK
# takes no lock of its own: one would have to be reset after a fork, and be
# taken in the same order as the logging module's.
_HANDLER = _StderrHandler()
_HANDLER.setFormatter(Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

# The level `get_logger` last put on the logger. A level that differs from it
# was set by someone else, and is kept (#108 review).
_applied_level = NOTSET


def get_logger() -> Logger:
    """The SDK's logger, with one stream handler for the whole process.

    Every client built without a ``logger=`` asks for it. The handler is
    attached only when the logger has none: a handler per call wrote every
    record once per client built (#104), and a handler the caller attached to
    ``marketdata.logger`` before the first client stands in for it.

    The SDK's handler takes its level from the settings on every call, as each
    new handler used to, and so does the logger, unless a level was set on it
    by someone else since: an application that set ``marketdata.logger`` to
    ``DEBUG`` got ``WARNING`` back from the next client built, and the
    handlers it had attached lost that logger's records below ``WARNING``
    (#108 review). A level set above the settings' drops the records below
    it before any handler sees them, the SDK's included. Two limits. A level
    set only on a parent logger (``marketdata``, or the root through
    ``basicConfig``) is not inherited, since the SDK gives its own logger the
    settings' level while it has none. And a level set to the one the SDK
    applied cannot be told apart from it, so it keeps following the settings.
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
