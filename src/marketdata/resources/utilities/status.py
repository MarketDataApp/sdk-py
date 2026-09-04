from pathlib import Path

from marketdata.api_error import api_error_handler
from marketdata.docs import docs
from marketdata.input_types.base import OutputFormat
from marketdata.output_types.utilities_status import ServiceStatus
from marketdata.resources.base import BaseResource
from marketdata.resources.utilities.base import render, resolve_output_params


@api_error_handler(check_status=False)
@docs
def status(
    self: BaseResource,
    *,
    output_format: OutputFormat | None = None,
    filename: str | Path | None = None,
) -> list[ServiceStatus] | dict | str:
    """
    Fetches the live status of every API service: whether it is online, its
    30 and 90 day uptime and when the status was last updated.

    The endpoint is free, needs no token and accepts no query parameters, so
    only `output_format` and `filename` apply.
    """
    user_universal_params = resolve_output_params(self, output_format, filename)
    self.logger.debug("Fetching API status...")

    response = self.client._make_request(
        method="GET",
        url="status/",
        include_api_version=False,
        check_rate_limits=False,
        populate_rate_limits=False,
    )

    return render(
        user_universal_params,
        response.json(),
        output_model=ServiceStatus,
        as_records=True,
        index_columns=["service"],
    )
