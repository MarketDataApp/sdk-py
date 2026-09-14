import datetime


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
GLOBAL_EXCLUDED_PARAMS = ["output_format", "filename"]
REFRESH_API_STATUS_INTERVAL = datetime.timedelta(minutes=4, seconds=30)
CACHE_VALIDITY_INTERVAL = datetime.timedelta(minutes=5)
ALLOWED_POSITIONAL_PARAMS = ["symbol", "symbols", "lookup"]
DATAFRAME_HANDLERS_PRIORITY = ["pandas", "polars"]
NO_TOKEN_VALUE = NoTokenValueType()
