from dataclasses import fields, is_dataclass
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

from httpx import Response

from marketdata.exceptions import ParseError
from marketdata.input_types.base import (
    BaseInputType,
    OutputFormat,
    UserUniversalAPIParams,
)
from marketdata.internal_settings import GLOBAL_EXCLUDED_PARAMS
from marketdata.output_handlers import get_dataframe_output_handler
from marketdata.settings import settings
from marketdata.utils import (
    column_key,
    csv_header,
    parse_json,
    validate_single_param,
)

if TYPE_CHECKING:
    from marketdata.client import MarketDataClient

NO_DATA_BODY = {"s": "no_data"}


def model_columns(output_model: type, requested: list[str] | None = None) -> list[str]:
    """The columns a result of ``output_model`` carries: every field but the
    API's status flag ``s``, or, under a ``columns=`` filter, the requested
    ones in request order, without duplicates (#87).

    A requested name matches a column of the model (case and spaces aside,
    so ``Expiration Date`` is ``Expiration_Date``) or, on a human-readable
    model, the API name at the same position of its ``api_model`` twin
    (``t`` selects ``Date``), which is how the API filters before renaming.
    Each human-readable model declares that twin as a ``ClassVar``, and
    ``test_output_types.py`` pins every pair. A column's own name wins over
    the positional map, which is what keeps ``MarketStatusHumanReadable``
    right: its columns are not in its twin's order, and both of its API names
    already match a column by name.

    **Known limit.** The API's endpoint-dependent aliases (``open`` for ``o``,
    ``price``, ``date``) are not mirrored: a name that matches nothing is
    ignored, and a filter that matches nothing leaves the full set rather than
    a frame with no columns. The API *does* resolve its own aliases, so for
    such a filter the empty result and a populated one no longer have the same
    shape: ``stocks.candles(columns=["open"])`` answers with the single column
    ``o`` and no index, while the empty frame keeps every model column and the
    ``t`` index. That is the one case #87 does not cover, pinned by
    ``test_status_mapping.py::test_an_api_alias_column_filter_does_not_keep_the_no_data_shape``.
    Mirroring the aliases would mean tracking a table the API changes per
    endpoint (``price`` even depends on whether the market is open).
    """
    if not is_dataclass(output_model):  # pragma: no cover - every model is one
        return []
    columns = [field.name for field in fields(output_model) if field.name != "s"]
    if not requested:
        return columns
    by_key = {column_key(name): name for name in columns}
    api_model = getattr(output_model, "api_model", None)
    if api_model is not None:
        api_columns = [field.name for field in fields(api_model) if field.name != "s"]
        # `strict`: a twin with another column count is a mistake in this
        # repository (test_output_types.py fails on it), and a partial map
        # would select the wrong columns without a word. The `ValueError` is
        # deliberately not an SDK exception: no answer of the API can cause it.
        for api_name, name in zip(api_columns, columns, strict=True):
            by_key.setdefault(column_key(api_name), name)
    selected: list[str] = []
    for name in requested:
        match = by_key.get(column_key(name))
        if match is not None and match not in selected:
            selected.append(match)
    return selected or columns


def no_data_result(
    user_universal_params: UserUniversalAPIParams,
    output_model: type,
    *,
    as_records: bool,
    index_columns: list[str] | None = None,
    response: Response | None = None,
):
    """The empty result for a 404 ``no_data`` answer (SDK requirements §9.1).

    An empty answer to a valid question is not an error, so every output
    format gets its natural empty value: a DataFrame with the model's columns
    and no rows, ``[]`` for list-shaped models and ``None`` for single-object
    models, the API's ``{"s": "no_data"}`` body as JSON, and a header-only CSV.
    The DataFrame and the CSV header carry the requested columns under a
    ``columns=`` filter, as a populated answer does (#87).
    """
    output_format = user_universal_params.output_format
    columns = model_columns(output_model, user_universal_params.columns)

    if output_format == OutputFormat.DATAFRAME:
        empty = {column: [] for column in columns}
        handler = get_dataframe_output_handler()
        return handler(empty, output_model, user_universal_params).get_result(
            index_columns=index_columns or []
        )

    if output_format == OutputFormat.INTERNAL:
        return [] if as_records else None

    if output_format == OutputFormat.JSON:
        # Only the JSON output echoes the API's body; a CSV placeholder body
        # (#89) is not JSON, so nothing is decoded on the other formats.
        #
        # A body that does not decode falls back to the canonical one rather
        # than raising: the status already classified this answer as empty, and
        # the other three output formats return their empty value for it. A
        # `ParseError` only here would make the output format decide whether a
        # call raises, which is exactly what #91 forbids. Reached when
        # something between the client and the API answers the 404 (a CDN, a
        # proxy, a gateway with no body).
        if response is None:
            return dict(NO_DATA_BODY)
        try:
            return parse_json(response)
        except ParseError:
            return dict(NO_DATA_BODY)

    if output_format == OutputFormat.CSV:
        # The caller who asked for no header gets an empty file, not a header.
        if user_universal_params.add_headers is False:
            return user_universal_params.write_file("")
        return user_universal_params.write_file(csv_header(columns))

    # Unreachable: the output format was validated by the Pydantic model.
    raise ValueError(f"Invalid output format: {output_format}")  # pragma: no cover


class BaseResource:
    def __init__(self, client: "MarketDataClient"):
        self.client = client
        self.logger = self.client.logger
        self.logger.debug(
            f"Initializing {self.__class__.__name__} API handler resource"
        )

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

        # Only default the filename when nobody supplied one. The validator mints a
        # timestamped path in output/ for None, so forcing None here unconditionally
        # threw away a caller-supplied (and already validated) filename (#60).
        result_data.setdefault("filename", None)
        user_universal_params = UserUniversalAPIParams.model_validate(result_data)

        # When using internal output format, we dont filter columns as the internal output format needs all columns
        if user_universal_params.output_format == OutputFormat.INTERNAL:
            user_universal_params.columns = None

        return user_universal_params
