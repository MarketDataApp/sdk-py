import datetime
import re

from pydantic import Field, field_validator, model_validator

from marketdata.input_types.base import BaseInputType, BaseModelConfig
from marketdata.utils import format_timestamp

_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


class StocksPricesInput(BaseInputType):
    model_config = BaseModelConfig

    symbols: str | list[str] = Field(
        description="A single symbol string or a list of symbol strings", min_length=1
    )

    @field_validator("symbols")
    def validate_symbols(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return value.split(",") if "," in value else [value]
        return value


class StocksQuotesInput(BaseInputType):
    model_config = BaseModelConfig

    symbols: str | list[str] = Field(
        description="A single symbol string or a list of symbol strings", min_length=1
    )

    use_52_week: bool | None = Field(
        description="Whether to use the 52 week high and low",
        default=None,
        alias="52week",
    )

    extended: bool | None = Field(
        description="Whether to use the extended quotes", default=None
    )


class StocksCandlesInput(BaseInputType):
    model_config = BaseModelConfig

    symbol: str = Field(description="The symbol to fetch candles for")

    resolution: str = Field(description="The resolution to use", default="D")

    from_date: datetime.date | datetime.datetime | str | None = Field(
        description="The start date to fetch candles for", default=None, alias="from"
    )

    to_date: datetime.date | datetime.datetime | str | None = Field(
        description="The end date to fetch candles for", default=None, alias="to"
    )

    countback: int | None = Field(
        description="The number of candles to fetch", default=None
    )

    extended: bool | None = Field(
        description="Whether to fetch extended candles", default=None
    )

    adjust_splits: bool | None = Field(
        description="Whether to adjust splits", default=None, alias="adjustsplits"
    )

    @model_validator(mode="after")
    def validate_input(self) -> "StocksCandlesInput":
        """Check the date range and, on an intraday resolution, turn dates into
        datetimes so the range can be split into requests.

        A string that starts with an ISO date is read as one. Any other string
        (``"yesterday"``, ``"60"``, a Unix time) is left for the API to
        resolve.

        Returns:
            The validated input.

        Raises:
            MinMaxDateValidationError: If ``from_date`` is after ``to_date``.
            ValueError: If an ISO-looking date is not a valid one.
        """
        self._validate_min_max_dates("from_date", "to_date")

        if self.is_intraday:
            if isinstance(self.from_date, str) and _ISO_DATE.match(self.from_date):
                self.from_date = format_timestamp(self.from_date)
            if isinstance(self.to_date, str) and _ISO_DATE.match(self.to_date):
                self.to_date = format_timestamp(self.to_date)

            if isinstance(self.from_date, datetime.date):
                self.from_date = datetime.datetime.combine(
                    self.from_date, datetime.time.min
                )
            if isinstance(self.to_date, datetime.date):
                self.to_date = datetime.datetime.combine(
                    self.to_date, datetime.time.min
                )
        return self

    @field_validator("resolution")
    def validate_resolution(cls, v: str) -> str:
        pattern = re.compile(
            r"^(?:"
            r"[1-9]\d*(?:[HDWMY])?"
            r"|[HDWMY]"
            r"|minutely|hourly|daily|weekly|monthly|yearly"
            r")$",
            re.IGNORECASE,
        )
        if not pattern.match(v):
            raise ValueError(f"Invalid resolution: {v}")
        return v

    @property
    def is_intraday(self) -> bool:
        # validate resolution is one of the following: minutely, hourly
        pattern = re.compile(
            r"^(?:" r"[1-9]\d*(?:[H])?" r"|[H]" r"|minutely|hourly" r")$", re.IGNORECASE
        )
        return pattern.match(self.resolution)


class StocksEarningsInput(BaseInputType):
    model_config = BaseModelConfig

    symbol: str = Field(description="The symbol to fetch earnings for")

    from_date: datetime.date | str | None = Field(
        description="The start date to fetch earnings for", default=None, alias="from"
    )

    to_date: datetime.date | str | None = Field(
        description="The end date to fetch earnings for", default=None, alias="to"
    )

    countback: int | None = Field(
        description="The number of earnings to fetch", default=None
    )

    date: datetime.date | str | None = Field(
        description="The date to fetch earnings for", default=None
    )

    report_type: str | None = Field(
        description="The type of earnings to fetch", default=None, alias="report"
    )

    @model_validator(mode="after")
    def validate_input(self) -> "StocksEarningsInput":
        self._validate_min_max_dates("from_date", "to_date")
        return self


class StocksNewsInput(BaseInputType):
    model_config = BaseModelConfig

    symbol: str = Field(description="The symbol to fetch news for")

    from_date: datetime.date | str | None = Field(
        description="The start date to fetch news for", default=None, alias="from"
    )

    to_date: datetime.date | str | None = Field(
        description="The end date to fetch news for", default=None, alias="to"
    )

    countback: int | None = Field(
        description="The number of news to fetch", default=None
    )

    date: datetime.date | str | None = Field(
        description="The date to fetch news for", default=None
    )

    @model_validator(mode="after")
    def validate_input(self) -> "StocksNewsInput":
        self._validate_min_max_dates("from_date", "to_date")
        return self
