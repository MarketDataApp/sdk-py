from abc import ABC, abstractmethod

# Timestamp column names (all lowercase for case-insensitive matching)
TIMESTAMP_COLUMN_NAMES = {
    "updated",
    "date",
    "t",
    "expiration",
    "expiration_date",
    "firsttraded",
    "first_traded",
    "publicationdate",
    "publication_date",
    "reportdate",
    "report_date",
}


class BaseOutputHandler(ABC):
    def __init__(self, data: list[dict] | dict, date_format=None):
        self.data = data
        self.date_format = date_format

    @abstractmethod
    def get_result(self, *args, **kwargs):
        raise NotImplementedError("Subclasses must implement this method")
