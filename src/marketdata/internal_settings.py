import datetime

import httpx


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
GLOBAL_EXCLUDED_PARAMS = ["output_format", "filename"]
REFRESH_API_STATUS_INTERVAL = datetime.timedelta(minutes=4, seconds=30)
CACHE_VALIDITY_INTERVAL = datetime.timedelta(minutes=5)
ALLOWED_POSITIONAL_PARAMS = ["symbol", "symbols", "lookup"]
DATAFRAME_HANDLERS_PRIORITY = ["pandas", "polars"]
NO_TOKEN_VALUE = NoTokenValueType()
