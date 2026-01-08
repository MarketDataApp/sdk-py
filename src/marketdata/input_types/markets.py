import datetime

from pydantic import Field, model_validator

from marketdata.input_types.base import BaseInputType, BaseModelConfig


class MarketStatusInput(BaseInputType):
    model_config = BaseModelConfig

    country: str | None = Field(
        default=None, description="The country to fetch the market status for"
    )

    date: datetime.date | str | None = Field(
        default=None, description="The date to fetch the market status for"
    )

    from_date: datetime.date | str | None = Field(
        default=None,
        description="The start date to fetch the market status for",
        alias="from",
    )

    to_date: datetime.date | str | None = Field(
        default=None,
        description="The end date to fetch the market status for",
        alias="to",
    )

    countback: int | None = Field(
        default=None, description="The number of days to fetch the market status for"
    )

    @model_validator(mode="after")
    def validate_input(self) -> "MarketStatusInput":
        self._validate_min_max_dates("from_date", "to_date")
        return self
