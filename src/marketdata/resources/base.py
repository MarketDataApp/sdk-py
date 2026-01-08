from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

from marketdata.input_types.base import (
    BaseInputType,
    OutputFormat,
    UserUniversalAPIParams,
)
from marketdata.internal_settings import GLOBAL_EXCLUDED_PARAMS
from marketdata.settings import settings
from marketdata.utils import validate_single_param

if TYPE_CHECKING:
    from marketdata.client import MarketDataClient


class BaseResource:
    def __init__(self, client: "MarketDataClient"):
        self.client = client
        self.logger = self.client.logger
        self.logger.info(f"Initializing {self.__class__.__name__} API handler resource")

    def _build_url(
        self,
        path: str,
        user_universal_params: UserUniversalAPIParams,
        input_params: BaseInputType,
        extra_params: dict[str, Any] | None = None,
        excluded_params: list[str] | None = None,
    ) -> str:
        url = path
        extra_params = extra_params or {}
        excluded_params = excluded_params or []

        user_universal_params_data = user_universal_params.model_dump(
            exclude_none=True, exclude_unset=True, by_alias=True
        )
        user_universal_params_data = {
            k: v
            for k, v in user_universal_params_data.items()
            if k not in excluded_params
        }
        input_params_data = input_params.model_dump(
            exclude_none=True, exclude_unset=True, by_alias=True
        )

        excluded_extra_params = [
            field for field in UserUniversalAPIParams.model_fields.keys()
        ]
        excluded_extra_params.extend(
            [field for field in input_params.__class__.model_fields.keys()]
        )

        input_params_data = {
            k: v for k, v in input_params_data.items() if k not in excluded_params
        }
        extra_params_data = {
            k: v
            for k, v in extra_params.items()
            if k not in excluded_params and k not in excluded_extra_params
        }
        params_data = {
            "format": user_universal_params.api_format,
        }
        params_data.update(user_universal_params_data)
        params_data.update(input_params_data)
        params_data.update(extra_params_data)

        params_data = {
            k: validate_single_param(k, v)
            for k, v in params_data.items()
            if k not in GLOBAL_EXCLUDED_PARAMS
        }

        params_string = urlencode(params_data)
        if params_string:
            url += f"?{params_string}"
        return url

    def _get_settings_params(self) -> UserUniversalAPIParams:
        settings_params_dict = {
            "output_format": settings.marketdata_output_format,
            "date_format": settings.marketdata_date_format,
            "columns": settings.marketdata_columns,
            "add_headers": settings.marketdata_add_headers,
            "use_human_readable": settings.marketdata_use_human_readable,
            "mode": settings.marketdata_mode,
        }
        settings_params_dict = {
            k: v for k, v in settings_params_dict.items() if v is not None
        }
        return UserUniversalAPIParams(**settings_params_dict)

    def _validate_user_universal_params(
        self,
        default_params: UserUniversalAPIParams,
        user_universal_params: UserUniversalAPIParams,
    ) -> UserUniversalAPIParams:
        settings_params_data = self._get_settings_params().model_dump(
            exclude_unset=True, exclude_none=True
        )
        default_params_data = default_params.model_dump(
            exclude_unset=True, exclude_none=True
        )
        user_universal_params_data = user_universal_params.model_dump(
            exclude_unset=True, exclude_none=True
        )

        result_data = settings_params_data
        result_data.update(default_params_data)
        result_data.update(user_universal_params_data)

        result_data["filename"] = None  # This will force filename to be populated
        user_universal_params = UserUniversalAPIParams.model_validate(result_data)

        # When using internal output format, we dont filter columns as the internal output format needs all columns
        if user_universal_params.output_format == OutputFormat.INTERNAL:
            user_universal_params.columns = None

        return user_universal_params
