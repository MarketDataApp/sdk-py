import datetime
import re

from pydantic import Field, field_validator, model_validator

from marketdata.input_types.base import BaseInputType, BaseModelConfig


class FundsCandlesInput(BaseInputType):
    model_config = BaseModelConfig

    symbol: str = Field(description="The symbol to fetch candles for")

    resolution: str = Field(description="The resolution to use", default="D")

    from_date: datetime.date | str | None = Field(
        description="The start date to fetch candles for", default=None, alias="from"
    )

    to_date: datetime.date | str | None = Field(
        description="The end date to fetch candles for", default=None, alias="to"
    )

    countback: int | None = Field(
        description="The number of candles to fetch", default=None
    )

    @model_validator(mode="after")
    def validate_input(self) -> "FundsCandlesInput":
        self._validate_min_max_dates("from_date", "to_date")
        return self

    @field_validator("resolution")
    def validate_resolution(cls, v: str) -> str:
        pattern = re.compile(
            r"^(?:"
            r"[1-9]\d*(?:[DWMY])?"
            r"|[DWMY]"
            r"|daily|weekly|monthly|yearly"
            r")$",
            re.IGNORECASE,
        )
        if not pattern.match(v):
            raise ValueError(f"Invalid resolution: {v}")
        return v
