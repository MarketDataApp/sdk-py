from collections.abc import Callable, Iterator
from contextlib import contextmanager
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
from marketdata.output_types.columns import _model_columns
from marketdata.settings import settings
from marketdata.utils import (
    csv_header,
    parse_error,
    parse_json,
    validate_single_param,
)

if TYPE_CHECKING:
    from marketdata.client import MarketDataClient

NO_DATA_BODY = {"s": "no_data"}


def model_columns(output_model: type, requested: list[str] | None = None) -> list[str]:
    """List the columns a result of an output model carries.

    Args:
        output_model: An output model.
        requested: The ``columns=`` filter. A name matches a column case- and
            space-insensitively by its column name, its field name or, on a
            human-readable model, the API name at the same position of its
            ``api_model`` twin. The API's own aliases (``open`` for ``o``) are
            not matched.

    Returns:
        Every column name, as the API spells it, in field order or, under a
        filter, the matched ones in request order without duplicates. The full
        list when no name matches, and an empty one for a class that is not a
        dataclass.

    Raises:
        ValueError: If a human-readable model and its ``api_model`` twin have
            different column counts.
    """
    return _model_columns(output_model, requested)


@contextmanager
def model_errors(response: Response) -> Iterator[None]:
    """Turn a model refusing a value into a ``ParseError``.

    A model raises ``TypeError`` or ``ValueError`` for a value it cannot
    hold: a price that is not a number, a date it cannot read. Those are the
    right answers for a model a caller builds by hand, and the wrong ones
    here, where the value came off the wire: a caller who wrote
    ``except BaseMarketdataException`` does not catch a built-in, so the
    output format decided whether a call raised, which #91 forbids (#50
    review).
    """
    try:
        yield
    except (TypeError, ValueError) as exc:
        raise parse_error(response, str(exc)) from exc


@contextmanager
def merged_model_errors(
    responses: list[Response], build_alone: Callable[[Response], object]
) -> Iterator[None]:
    """``model_errors`` for a result merged from the answers of several
    requests: the chunks of ``stocks.candles``, the symbols of
    ``options.quotes``.

    The ``ParseError`` names the answer a refused value came from, with that
    answer's own refusal: its URL, status, request id and body excerpt are
    what support reads, and the last answer of a merge is usually a healthy
    one (#50 review). Finding it costs nothing while the call works: only
    after a refusal is each answer built again on its own, in request order,
    and the first one refused is named with the reason it was refused for.
    That is not always the reason the merge was refused for, since two
    answers can each carry a bad value in a different field. A refusal no
    answer produces alone could only come from the merge, which no model does
    today; the last answer is named then, with the merge's reason.
    """
    try:
        yield
    except (TypeError, ValueError) as exc:
        response, reason = _first_refusal(responses, build_alone) or (
            responses[-1],
            exc,
        )
        raise parse_error(response, str(reason)) from reason


def _first_refusal(
    responses: list[Response], build_alone: Callable[[Response], object]
) -> tuple[Response, Exception] | None:
    for response in responses:
        try:
            build_alone(response)
        except Exception as refusal:  # any failure to build it alone locates it
            return response, refusal
    return None


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
            body = parse_json(response)
        except ParseError:
            return dict(NO_DATA_BODY)
        # The CSV placeholder `""` (#89) is also a JSON document, the empty
        # string, and reaches here whatever format was asked for: only an
        # object is the API's body to echo.
        return body if isinstance(body, dict) else dict(NO_DATA_BODY)

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
