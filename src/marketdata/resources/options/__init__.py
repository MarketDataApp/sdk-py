from marketdata.resources.base import BaseResource
from marketdata.resources.options.chain import chain
from marketdata.resources.options.expirations import expirations
from marketdata.resources.options.lookup import lookup
from marketdata.resources.options.quotes import quotes
from marketdata.resources.options.strikes import strikes


class OptionsResource(BaseResource):
    chain = chain
    expirations = expirations
    lookup = lookup
    quotes = quotes
    strikes = strikes


__all__ = ["OptionsResource"]
