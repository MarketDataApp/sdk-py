from dataclasses import dataclass


@dataclass
class OptionsLookup:
    s: str
    optionSymbol: str

    def __repr__(self) -> str:
        return f"OptionSymbol: {self.optionSymbol}"

    def __str__(self) -> str:
        return self.__repr__()


@dataclass
class OptionsLookupHumanReadable:
    Symbol: str

    def __repr__(self) -> str:
        return f"Symbol: {self.Symbol}"

    def __str__(self) -> str:
        return self.__repr__()


# The API-named twin of the human-readable model, same fields in the same
# order: a `columns=` filter written in API names is translated to the
# human-readable columns by position (#87). Set outside the class so it is
# not a dataclass field.
OptionsLookupHumanReadable.api_model = OptionsLookup
