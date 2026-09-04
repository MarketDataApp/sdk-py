from pathlib import Path

from marketdata.api_error import api_error_handler
from marketdata.docs import docs
from marketdata.input_types.base import OutputFormat
from marketdata.output_types.utilities_user import User
from marketdata.resources.base import BaseResource
from marketdata.resources.utilities.base import render, resolve_output_params


@api_error_handler(check_status=False)
@docs
def user(
    self: BaseResource,
    *,
    output_format: OutputFormat | None = None,
    filename: str | Path | None = None,
) -> User | dict | str:
    """
    Fetches the authenticated account's credit limit, remaining credits and
    options data permissions. The call is free, is never blocked by the
    pre-flight rate-limit check, and refreshes the client's rate-limit state
    from the response headers.

    The endpoint requires a token and only `output_format` and `filename`
    apply.
    """
    user_universal_params = resolve_output_params(self, output_format, filename)
    self.logger.debug("Fetching user info...")

    response = self.client._make_request(
        method="GET",
        url="user/",
        include_api_version=False,
        check_rate_limits=False,
        populate_rate_limits=True,
    )

    return render(
        user_universal_params,
        response.json(),
        output_model=User,
        as_records=False,
    )
