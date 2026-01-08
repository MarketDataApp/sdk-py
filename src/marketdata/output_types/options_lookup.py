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
