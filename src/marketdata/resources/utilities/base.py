"""Shared plumbing for the utilities resource.

The three utilities endpoints live at the API root, take no query parameters
(``/status/`` and ``/headers/`` answer 404 to any) and only speak JSON, so
they bypass the ``universal_params`` machinery: the only universal parameters
that apply are ``output_format`` and ``filename``, and every output format is
produced client-side from the decoded JSON.
"""

from pathlib import Path
from typing import Any

from httpx import Response

from marketdata.input_types.base import OutputFormat, UserUniversalAPIParams
from marketdata.output_handlers import get_dataframe_output_handler
from marketdata.resources.base import BaseResource, no_data_result
from marketdata.utils import dict_to_csv, get_data_records, is_no_data, parse_json


def resolve_output_params(
    resource: BaseResource,
    output_format: OutputFormat | None,
    filename: str | Path | None,
) -> UserUniversalAPIParams:
    """Apply the settings < client defaults < call cascade to the two
    universal parameters these endpoints honor."""
    requested: dict[str, Any] = {}
    if output_format is not None:
        requested["output_format"] = output_format
    if filename is not None:
        requested["filename"] = filename
    return resource._validate_user_universal_params(
        resource.client.default_params,
        UserUniversalAPIParams.model_validate(requested),
    )


def render(
    user_universal_params: UserUniversalAPIParams,
    response: Response,
    *,
    output_model: type,
    as_records: bool,
    index_columns: list[str] | None = None,
):
    """Turn the response into the requested output format.

    ``as_records`` distinguishes column-oriented payloads (one row per entry,
    like ``/status/``) from flat objects (``/headers/``, ``/user/``).
    """
    output_format = user_universal_params.output_format

    if is_no_data(response):
        return no_data_result(
            user_universal_params,
            output_model,
            as_records=as_records,
            index_columns=index_columns,
            body=parse_json(response),
        )
    data = parse_json(response)

    if output_format == OutputFormat.DATAFRAME:
        handler = get_dataframe_output_handler()
        return handler(data, output_model, user_universal_params).get_result(
            index_columns=index_columns or []
        )

    elif output_format == OutputFormat.INTERNAL:
        if as_records:
            rows = get_data_records(data, exclude_keys=["s"])
            return [output_model(**row) for row in rows]
        return output_model.from_dict(data)

    elif output_format == OutputFormat.JSON:
        return data

    elif output_format == OutputFormat.CSV:
        return user_universal_params.write_file(dict_to_csv(data, exclude_keys=["s"]))

    # Unreachable: the output format was validated by the Pydantic model, but
    # the branch keeps the type checker honest.
    raise ValueError(f"Invalid output format: {output_format}")  # pragma: no cover
