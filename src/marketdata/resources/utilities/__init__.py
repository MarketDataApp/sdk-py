from marketdata.resources.base import BaseResource
from marketdata.resources.utilities.delete_token import delete_token
from marketdata.resources.utilities.headers import headers
from marketdata.resources.utilities.status import status
from marketdata.resources.utilities.user import user


class UtilitiesResource(BaseResource):
    status = status
    headers = headers
    user = user
    delete_token = delete_token


__all__ = ["UtilitiesResource"]
