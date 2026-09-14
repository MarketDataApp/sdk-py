import datetime

import httpx
from httpx import Response


class NoTokenValueType:
    pass


MAX_CONCURRENT_REQUESTS = 50
MAX_RETRY_ATTEMPTS = 3
INITIAL_RETRY_DELAY = 1.0
# SDK requirements §10: one fixed request timeout, 99 seconds, with a 2 second
# connect timeout where the HTTP client supports one. It is deliberately not
# configurable: a caller who wants to give up sooner cancels the call rather
# than shortening this.
#
# httpx applies each field to one operation, not to the call as a whole:
# `connect` bounds opening the connection, `read` the wait for each chunk of
# the answer, `write` the upload of a request body, and `pool` the wait for a
# free connection. A server that trickles bytes can still hold a request open
# past 99 seconds; bounding that needs a clock of our own, not a timeout.
#
# The name changed with the type (#64). It was `HTTP_TIMEOUT = 60`, an int
# that `stocks.candles` also handed to `future.result(timeout=...)`, where an
# `httpx.Timeout` raises `TypeError` from inside a worker thread. Renaming it
# turns any importer that was not updated into an `ImportError` at merge.
REQUEST_TIMEOUT = httpx.Timeout(99.0, connect=2.0)
VALID_STATUS_CODES = [200, 203]
# The longest credit window the API bills over is a day, so a reset time older
# than that is a value the SDK could not read rather than a window that closed
# (#42).
MAX_CREDIT_WINDOW_SECONDS = 24 * 60 * 60

# The API's IP headers (#44). httpx matches header names case-insensitively,
# so the lowercase spelling reads them whatever case the API sends. The legacy
# `X-API-BLOCKED-IP` carries whichever of the two applies and is deliberately
# not read: the API is removing it (MarketData-App/api#202).
HEADER_DETECTED_IP = "x-api-detected-ip"
HEADER_AUTHORIZED_IP = "x-api-authorized-ip"


def read_header(response: Response | None, name: str) -> str | None:
    """One header's value, or ``None`` when there is nothing to read.

    A header the API sent blank is nothing: ``''`` would read as an address to
    a caller checking ``if error.authorized_ip``. The rule lives here so the
    two sites that read an IP header, and anything that joins them, answer the
    same way. ``_request_id`` in ``exceptions.py`` keeps its own reading: it
    answers ``N/A`` rather than ``None``, and changing what it makes of a blank
    ``cf-ray`` is a change to the support block, not a cleanup (#114).
    """
    if response is None:
        return None
    value = response.headers.get(name)
    return (value or "").strip() or None


GLOBAL_EXCLUDED_PARAMS = ["output_format", "filename"]
REFRESH_API_STATUS_INTERVAL = datetime.timedelta(minutes=4, seconds=30)
CACHE_VALIDITY_INTERVAL = datetime.timedelta(minutes=5)
ALLOWED_POSITIONAL_PARAMS = ["symbol", "symbols", "lookup"]
DATAFRAME_HANDLERS_PRIORITY = ["pandas", "polars"]
NO_TOKEN_VALUE = NoTokenValueType()
