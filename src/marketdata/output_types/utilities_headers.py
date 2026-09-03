from dataclasses import dataclass, field


@dataclass
class RequestHeaders:
    """The request headers as the API received them, from ``GET /headers/``.

    Header names are normalized to lowercase. The API masks the token in the
    ``authorization`` value before echoing it back.
    """

    headers: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "RequestHeaders":
        return cls(headers={str(k).lower(): v for k, v in data.items()})

    def get(self, name: str, default: str | None = None) -> str | None:
        return self.headers.get(name.lower(), default)

    @property
    def detected_ip(self) -> str | None:
        """The caller's IP as seen by the API; what an IP allow-list must contain."""
        return self.get("cf-connecting-ip") or self.get("x-real-ip")

    @property
    def user_agent(self) -> str | None:
        return self.get("user-agent")

    @property
    def authorization(self) -> str | None:
        return self.get("authorization")

    def __repr__(self) -> str:
        lines = [f"{name}: {value}" for name, value in sorted(self.headers.items())]
        return "Request Headers:\n" + "\n".join(lines)

    def __str__(self) -> str:
        return self.__repr__()
