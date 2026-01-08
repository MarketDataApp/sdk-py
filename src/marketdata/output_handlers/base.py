from abc import ABC, abstractmethod


class BaseOutputHandler(ABC):
    def __init__(self, data: list[dict] | dict):
        self.data = data

    @abstractmethod
    def get_result(self, *args, **kwargs):
        raise NotImplementedError("Subclasses must implement this method")
