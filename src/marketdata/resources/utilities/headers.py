from pathlib import Path

from marketdata.api_error import api_error_handler
from marketdata.docs import docs
from marketdata.input_types.base import OutputFormat
from marketdata.output_types.utilities_headers import RequestHeaders
from marketdata.resources.base import BaseResource
from marketdata.resources.utilities.base import render, resolve_output_params


@api_error_handler(check_status=False)
@docs
def headers(
    self: BaseResource,
    *,
    output_format: OutputFormat | None = None,
    filename: str | Path | None = None,
) -> RequestHeaders | dict | str:
    """
    Echoes the request headers as the API received them, including the IP
    the API detected. Useful to debug proxies and IP allow-lists. The token in
    the `authorization` header is masked by the API.

    The endpoint is free, needs no token and accepts no query parameters, so
    only `output_format` and `filename` apply.
    """
    user_universal_params = resolve_output_params(self, output_format, filename)
    self.logger.debug("Fetching request headers...")

    response = self.client._make_request(
        method="GET",
        url="headers/",
        include_api_version=False,
        check_rate_limits=False,
        populate_rate_limits=False,
    )

    return render(
        user_universal_params,
        response.json(),
        output_model=RequestHeaders,
        as_records=False,
    )
