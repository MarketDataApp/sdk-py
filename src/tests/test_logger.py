"""The SDK's stream handler (#104): one for the process, however many clients
are built, and none added by importing the package."""

import logging
import os
import subprocess
import sys

from marketdata.logger import get_logger

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
