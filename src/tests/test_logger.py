"""The SDK's stream handler (#104): one for the process, however many clients
are built, and none added by importing the package."""

import contextlib
import io
import logging
import os
import subprocess
import sys
import threading

from marketdata.logger import get_logger
from marketdata.settings import settings

LOGGER_NAME = "marketdata.logger"

# Run in a fresh interpreter: the handler count is process state, and every
# test in this session builds clients.
FRESH_PROCESS = """
import logging

import respx

import marketdata

logger = logging.getLogger("marketdata.logger")
print(len(logger.handlers))
with respx.mock(assert_all_called=False) as mock:
    mock.get(url__regex=r".*").respond(json={}, status_code=200)
    marketdata.MarketDataClient(token="x" * 30)
    marketdata.MarketDataClient(token="x" * 30)
print(len(logger.handlers))
logger.warning("one record")
"""


def test_a_process_gets_one_handler_and_one_line_per_record():
    """Measured before the fix: 1 handler after `import marketdata`, 2 after
    one client and 3 after a second, so each record reached stderr once per
    handler."""
    result = subprocess.run(
        [sys.executable, "-c", FRESH_PROCESS],
        capture_output=True,
        text=True,
        timeout=120,
        env={**os.environ, "MARKETDATA_LOGGING_LEVEL": "INFO"},
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["0", "1"]
    assert result.stderr.count("one record") == 1


def test_get_logger_adds_its_handler_once():
    logger = get_logger()
    count = len(logger.handlers)

    get_logger()
    get_logger()

    assert count >= 1
    assert len(logger.handlers) == count


def test_a_handler_the_caller_attached_stands_in_for_the_sdks(monkeypatch):
    logger = logging.getLogger(LOGGER_NAME)
    mine = logging.NullHandler()
    monkeypatch.setattr(logger, "handlers", [mine])

    get_logger()

    assert logger.handlers == [mine]


def test_the_handler_writes_to_the_stderr_of_the_moment(monkeypatch, capsys):
    """With one handler for the process, the stream cannot be fixed when it is
    built: a first client built under a redirected stderr would otherwise take
    every later line with it (a captured test, `redirect_stderr`)."""
    logger = logging.getLogger(LOGGER_NAME)
    monkeypatch.setattr(logger, "handlers", [])
    monkeypatch.setattr(settings, "marketdata_logging_level", "WARNING")
    redirected = io.StringIO()

    with contextlib.redirect_stderr(redirected):
        get_logger()
    logger.warning("after the redirect")

    assert "after the redirect" in capsys.readouterr().err
    assert redirected.getvalue() == ""


def test_the_handler_takes_a_stream_set_on_it(monkeypatch):
    """`StreamHandler.setStream` is public, and an application may point its
    stream handlers somewhere else: the current stderr is only the default."""
    logger = logging.getLogger(LOGGER_NAME)
    monkeypatch.setattr(logger, "handlers", [])
    monkeypatch.setattr(settings, "marketdata_logging_level", "WARNING")
    handler = get_logger().handlers[0]
    mine = io.StringIO()

    try:
        handler.setStream(mine)
        logger.warning("to my stream")
    finally:
        handler.setStream(None)

    assert "to my stream" in mine.getvalue()
    assert handler.stream is sys.stderr


def test_the_handler_keeps_the_level_of_the_settings(monkeypatch, capsys):
    """Each handler used to carry the settings' level, so a caller lowering the
    logger's own level did not open the SDK's stream to DEBUG. The one handler
    keeps doing that, and follows the settings each time a client asks."""
    logger = logging.getLogger(LOGGER_NAME)
    level = logger.level
    monkeypatch.setattr(logger, "handlers", [])
    monkeypatch.setattr(settings, "marketdata_logging_level", "WARNING")
    try:
        get_logger()
        logger.setLevel(logging.DEBUG)
        logger.debug("not for the SDK's stream")
        assert "not for the SDK's stream" not in capsys.readouterr().err

        monkeypatch.setattr(settings, "marketdata_logging_level", "DEBUG")
        get_logger()
        logger.debug("now it is")
        assert "now it is" in capsys.readouterr().err
    finally:
        logger.setLevel(level)


def test_clients_built_at_once_attach_one_handler(monkeypatch):
    """Sixteen threads released together all see a logger with no handler.
    Only one handler ends up attached, because it is always the same one and
    `addHandler` does not add a handler twice. Repeated, since a race shows
    up in some rounds only."""
    logger = logging.getLogger(LOGGER_NAME)
    for _ in range(20):
        monkeypatch.setattr(logger, "handlers", [])
        barrier = threading.Barrier(16)

        def build():
            barrier.wait()
            get_logger()

        threads = [threading.Thread(target=build) for _ in range(16)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert len(logger.handlers) == 1
