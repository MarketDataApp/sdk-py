from pydantic import BaseModel, ConfigDict
from pydantic_settings import BaseSettings

from marketdata.input_types.base import DateFormat, Mode, OutputFormat
from marketdata.internal_settings import NO_TOKEN_VALUE, NoTokenValueType


class UniversalParamsSettings(BaseModel):
    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    marketdata_output_format: OutputFormat | None = None
    marketdata_date_format: DateFormat | None = None
    marketdata_columns: list[str] | None = None
    marketdata_add_headers: bool | None = None
    marketdata_use_human_readable: bool | None = None
    marketdata_mode: Mode | None = None


class NoTokenValue:
    pass


class MarketDataSettings(BaseSettings, UniversalParamsSettings):
    marketdata_token: str | NoTokenValueType = NO_TOKEN_VALUE
    marketdata_base_url: str = "https://api.marketdata.app"
    marketdata_api_version: str = "v1"
    marketdata_logging_level: str = "INFO"

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = MarketDataSettings()
