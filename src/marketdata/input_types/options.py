import datetime
from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from marketdata.input_types.base import BaseInputType, BaseModelConfig
from marketdata.input_types.filters import render_number


class OptionsExpirationsInput(BaseInputType):
    model_config = BaseModelConfig

    symbol: str = Field(..., description="The symbol to fetch expirations for")
    strike: float | None = Field(
        description="The strike price to filter by", default=None
    )
    date: datetime.date | str | None = Field(
        description="The date to fetch expirations for", default=None
    )


class OptionsChainInput(BaseInputType):
    model_config = BaseModelConfig

    symbol: str | None = Field(
        description="The symbol to fetch options chain for", default=None
    )

    # Expiration filters
    date: datetime.date | str | None = Field(
        description="The date to fetch options chain for", default=None
    )
    expiration: datetime.date | Literal["all", "ALL"] | None = Field(
        description="The expiration date to filter by", default=None
    )
    days_to_expiration: int | None = Field(
        description="The number of days to expiration to filter by",
        alias="dte",
        default=None,
    )
    from_date: datetime.date | str | None = Field(
        description="The start date to fetch options chain for",
        default=None,
        alias="from",
    )
    to_date: datetime.date | str | None = Field(
        description="The end date to fetch options chain for",
        default=None,
        alias="to",
    )
    month: int | None = Field(description="The month to filter by", default=None)
    year: int | None = Field(description="The year to filter by", default=None)
    weekly: bool | None = Field(
        description="Whether to filter by weekly options", default=None
    )
    monthly: bool | None = Field(
        description="Whether to filter by monthly options", default=None
    )
    quarterly: bool | None = Field(
        description="Whether to filter by quarterly options", default=None
    )

    # Strike filters
    # `StrikeFilter` is a `str`, so it needs no place of its own here.
    strike: str | int | float | Decimal | None = Field(
        description=(
            "The strikes to filter by: a price, or an expression built with "
            "`StrikeFilter` (exact, any_of, between, at_least, at_most, above, "
            "below, expression)"
        ),
        default=None,
    )
    # `DeltaFilter` is a `str`, so it needs no place of its own here.
    delta: str | int | float | Decimal | None = Field(
        description=(
            "The delta to filter by: a number, or an expression built with "
            "`DeltaFilter`. The API filters on the absolute value and answers "
            "both sides"
        ),
        default=None,
    )
    strike_limit: int | None = Field(
        description="The strike limit to filter by", alias="strikeLimit", default=None
    )
    range: str | None = Field(description="The range to filter by", default=None)

    # Price / liquidity filters
    min_bid: float | None = Field(
        description="The minimum bid price to filter by", alias="minBid", default=None
    )
    max_bid: float | None = Field(
        description="The maximum bid price to filter by", alias="maxBid", default=None
    )
    min_ask: float | None = Field(
        description="The minimum ask price to filter by", alias="minAsk", default=None
    )
    max_ask: float | None = Field(
        description="The maximum ask price to filter by", alias="maxAsk", default=None
    )
    max_bid_ask_spread: float | None = Field(
        default=None,
        description="The maximum bid-ask spread to filter by",
        alias="maxBidAskSpread",
    )
    max_bid_ask_spread_pct: float | None = Field(
        default=None,
        description="The maximum bid-ask spread percentage to filter by",
        alias="maxBidAskSpreadPct",
    )
    min_open_interest: int | None = Field(
        default=None,
        description="The minimum open interest to filter by",
        alias="minOpenInterest",
    )
    min_volume: int | None = Field(
        description="The minimum volume to filter by", alias="minVolume", default=None
    )

    # Other filters
    nonstandard: bool | None = Field(
        description="Whether to include non-standard contracts", default=None
    )
    side: str | None = Field(description="The side to filter by", default=None)
    am: bool | None = Field(
        description="Whether to include A.M. expirations", default=None
    )
    pm: bool | None = Field(
        description="Whether to include P.M. expirations", default=None
    )

    @field_validator("strike", "delta", mode="before")
    def render_number_filter(cls, value: object, info) -> object:
        """A bare number is checked and rendered the way a filter is.

        `urlencode` stringifies a number on its own, so this is not about the
        digits: it is the refusals. A bool would travel as `True`, an infinity
        as `inf`, and a negative strike would come back as its absolute value
        with no word from the API (#101). A `str`, which a filter is, travels
        as written.
        """
        if value is None or isinstance(value, str):
            return value
        return render_number(value, info.field_name)

    @field_validator("expiration")
    def validate_expiration(
        cls, value: datetime.date | Literal["all", "ALL"] | None
    ) -> datetime.date | Literal["all", "ALL"] | None:
        if isinstance(value, str):
            value = value.lower()
        return value

    @model_validator(mode="after")
    def validate_input(self) -> "OptionsChainInput":
        params_tuples = [
            ("min_bid", "max_bid"),
            ("min_ask", "max_ask"),
        ]
        for min_param, max_param in params_tuples:
            self._validate_min_max_value(min_param, max_param)
        return self


class OptionsQuotesInput(BaseInputType):
    model_config = BaseModelConfig

    symbols: str | list[str] = Field(
        description="A single symbol string or a list of symbol strings", min_length=1
    )
    date: datetime.date | str | None = Field(
        description="Historical end-of-day quote date (ISO 8601, unix, or spreadsheet)",
        default=None,
    )
    from_date: datetime.date | str | None = Field(
        description="Start of date range, inclusive (ISO 8601, unix, or spreadsheet)",
        default=None,
        alias="from",
    )
    to_date: datetime.date | str | None = Field(
        description="End of date range, exclusive (ISO 8601, unix, or spreadsheet)",
        default=None,
        alias="to",
    )

    @field_validator("symbols")
    def validate_symbols(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return value.split(",") if "," in value else [value]
        return value

    @model_validator(mode="after")
    def validate_input(self) -> "OptionsQuotesInput":
        self._validate_min_max_dates("from_date", "to_date")
        return self


class OptionsStrikesInput(BaseInputType):
    model_config = BaseModelConfig

    symbol: str = Field(..., description="The symbol to fetch strikes for")
    expiration: datetime.date | str | None = Field(
        description="The expiration date to filter by", default=None
    )
    date: datetime.date | str | None = Field(
        description="The date to fetch strikes for", default=None
    )


class LookupOptionSide(str, Enum):
    CALL = "call"
    PUT = "put"
    BOTH = "both"


class OptionsLookupInput(BaseInputType):
    model_config = BaseModelConfig

    lookup: str = Field(
        ..., description="The lookup string to lookup options for", min_length=1
    )
