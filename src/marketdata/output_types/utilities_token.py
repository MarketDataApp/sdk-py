from dataclasses import dataclass


@dataclass
class TokenDeleted:
    """The envelope of ``DELETE /v1/user/token/``: whether the token was deleted."""

    s: str

    @classmethod
    def from_dict(cls, data: dict) -> "TokenDeleted":
        """Build from the decoded body, keeping only the key this model
        declares. A body without ``s`` leaves the constructor without it,
        which raises ``TypeError`` rather than the ``KeyError`` a direct
        index would, so ``model_errors`` turns it into ``ParseError`` like
        every other value an ``INTERNAL`` model refuses."""
        return cls(**{key: value for key, value in data.items() if key == "s"})

    def __repr__(self) -> str:
        return f"Token Deleted: {self.s}"

    def __str__(self) -> str:
        return self.__repr__()
