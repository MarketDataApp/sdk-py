import datetime

from httpx import Response


class NoTokenValueType:
    pass


MAX_CONCURRENT_REQUESTS = 50
MAX_RETRY_ATTEMPTS = 3
INITIAL_RETRY_DELAY = 1.0
HTTP_TIMEOUT = 60
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
