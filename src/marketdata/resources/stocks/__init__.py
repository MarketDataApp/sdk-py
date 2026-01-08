from marketdata.resources.base import BaseResource
from marketdata.resources.stocks.candles import candles
from marketdata.resources.stocks.earnings import earnings
from marketdata.resources.stocks.news import news
from marketdata.resources.stocks.prices import prices
from marketdata.resources.stocks.quotes import quotes


class StocksResource(BaseResource):
    candles = candles
    earnings = earnings
    news = news
    prices = prices
    quotes = quotes


__all__ = ["StocksResource"]
