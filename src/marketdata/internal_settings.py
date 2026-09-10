import datetime


class NoTokenValueType:
    pass


MAX_CONCURRENT_REQUESTS = 50
MAX_RETRY_ATTEMPTS = 3
INITIAL_RETRY_DELAY = 1.0
HTTP_TIMEOUT = 60
VALID_STATUS_CODES = [200, 203]
# The API's IP headers (#44). httpx matches header names case-insensitively,
# so the lowercase spelling reads them whatever case the API sends. The legacy
# `X-API-BLOCKED-IP` carries whichever of the two applies and is deliberately
# not read: the API is removing it (MarketData-App/api#202).
HEADER_DETECTED_IP = "x-api-detected-ip"
HEADER_AUTHORIZED_IP = "x-api-authorized-ip"
GLOBAL_EXCLUDED_PARAMS = ["output_format", "filename"]
REFRESH_API_STATUS_INTERVAL = datetime.timedelta(minutes=4, seconds=30)
CACHE_VALIDITY_INTERVAL = datetime.timedelta(minutes=5)
ALLOWED_POSITIONAL_PARAMS = ["symbol", "symbols", "lookup"]
DATAFRAME_HANDLERS_PRIORITY = ["pandas", "polars"]
NO_TOKEN_VALUE = NoTokenValueType()
