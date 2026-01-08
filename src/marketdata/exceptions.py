"""Exceptions for the MarketData Python SDK"""


class RateLimitError(Exception):
    pass


class KeywordOnlyArgumentError(Exception):
    pass


class BadStatusCodeError(Exception):
    pass


class RequestError(Exception):
    pass


class InvalidStatusDataError(Exception):
    pass


class MinMaxDateValidationError(Exception):
    pass
