import datetime


class NoTokenValueType:
    pass


MAX_CONCURRENT_REQUESTS = 50
MAX_RETRY_ATTEMPTS = 3
RETRY_BACKOFF = 0.5
RETRY_STATUS_CODES = lambda x: x > 500
HTTP_TIMEOUT = 60
MIN_RETRY_BACKOFF = 0.5
MAX_RETRY_BACKOFF = 5
VALID_STATUS_CODES = [200, 203]
GLOBAL_EXCLUDED_PARAMS = ["output_format", "filename"]
REFRESH_API_STATUS_INTERVAL = datetime.timedelta(minutes=4, seconds=30)
ALLOWED_POSITIONAL_PARAMS = ["symbol", "symbols", "lookup"]
DATAFRAME_HANDLERS_PRIORITY = ["pandas", "polars"]
NO_TOKEN_VALUE = NoTokenValueType()
