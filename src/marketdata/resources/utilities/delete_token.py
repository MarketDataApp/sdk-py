from pathlib import Path

from marketdata.api_error import api_error_handler
from marketdata.docs import docs
from marketdata.input_types.base import OutputFormat
from marketdata.output_types.utilities_token import TokenDeleted
from marketdata.resources.base import BaseResource
from marketdata.resources.utilities.base import render, resolve_output_params


@api_error_handler(check_status=False)
@docs
def delete_token(
    self: BaseResource,
    *,
    output_format: OutputFormat | None = None,
    filename: str | Path | None = None,
) -> TokenDeleted | dict | str:
    """
    Revokes the authenticated account's API token. The token used to make
    this call is unusable for any further request once it answers.

    The endpoint requires a token and only `output_format` and `filename`
    apply.
    """
    user_universal_params = resolve_output_params(self, output_format, filename)
    self.logger.debug("Deleting API token...")

    response = self.client._make_request(
        method="DELETE",
        url="user/token/",
    )

    return render(
        user_universal_params,
        response,
        output_model=TokenDeleted,
        as_records=False,
    )
