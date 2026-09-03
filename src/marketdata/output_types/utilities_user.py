from dataclasses import dataclass

# The API body still uses the old "requests" wording; the SDK exposes the
# fields under the API-credits nomenclature (SDK requirements §8.1).
_FIELD_MAP = {
    "x-ratelimit-requests-limit": "credit_limit",
    "x-ratelimit-requests-remaining": "credits_remaining",
    "x-options-data-permissions": "options_data_permissions",
}


@dataclass
class User:
    """The authenticated account's plan counters, from ``GET /user/``."""

    credit_limit: int
    credits_remaining: int
    options_data_permissions: str

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        return cls(
            **{
                _FIELD_MAP[key]: value
                for key, value in data.items()
                if key in _FIELD_MAP
            }
        )

    @property
    def has_options_data(self) -> bool:
        return bool(self.options_data_permissions)

    def __repr__(self) -> str:
        permissions = self.options_data_permissions or "none"
        return (
            f"User: {self.credits_remaining}/{self.credit_limit} credits remaining,"
            f" options data: {permissions}"
        )

    def __str__(self) -> str:
        return self.__repr__()
