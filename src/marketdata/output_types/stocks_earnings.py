import datetime
from dataclasses import dataclass

from marketdata.utils import format_timestamp


@dataclass
class StockEarnings:
    s: str
    symbol: list[str]
    fiscalYear: list[int]
    fiscalQuarter: list[int]
    date: list[datetime.datetime]
    reportDate: list[datetime.datetime]
    reportTime: list[str]
    currency: list[str]
    reportedEPS: list[float]
    estimatedEPS: list[float]
    surpriseEPS: list[float]
    surpriseEPSpct: list[float]
    updated: list[datetime.datetime]

    def __post_init__(self):
        self.updated = [format_timestamp(updated) for updated in self.updated]
        self.date = [format_timestamp(date) for date in self.date]
        self.reportDate = [
            format_timestamp(reportDate) for reportDate in self.reportDate
        ]

    def __repr__(self) -> str:
        _format_dates = lambda dates: [date.strftime("%Y-%m-%d") for date in dates]
        result = f"Stock Earnings:\n"
        result += f"Symbol: {self.symbol}\n"
        result += f"Fiscal Year: {self.fiscalYear}\n"
        result += f"Fiscal Quarter: {self.fiscalQuarter}\n"
        result += f"Date: {_format_dates(self.date)}\n"
        result += f"Report Date: {_format_dates(self.reportDate)}\n"
        result += f"Report Time: {self.reportTime}\n"
        result += f"Currency: {self.currency}\n"
        result += f"Reported EPS: {self.reportedEPS}\n"
        result += f"Estimated EPS: {self.estimatedEPS}\n"
        result += f"Surprise EPS: {self.surpriseEPS}\n"
        result += f"Surprise EPS Percent: {self.surpriseEPSpct}\n"
        result += f"Updated: {_format_dates(self.updated)}\n"
        return result

    def __str__(self) -> str:
        return self.__repr__()

    @classmethod
    def from_dict(cls, data: dict) -> "StockEarnings":
        return cls(**data)


@dataclass
class StockEarningsHumanReadable:
    Symbol: list[str]
    Fiscal_Year: list[int]
    Fiscal_Quarter: list[int]
    Date: list[datetime.datetime]
    Report_Date: list[datetime.datetime]
    Report_Time: list[str]
    Currency: list[str]
    Reported_EPS: list[float]
    Estimated_EPS: list[float]
    Surprise_EPS: list[float]
    Surprise_EPS_Percent: list[float]
    Updated: list[datetime.datetime]

    def __post_init__(self):
        self.Updated = [format_timestamp(updated) for updated in self.Updated]
        self.Date = [format_timestamp(date) for date in self.Date]
        self.Report_Date = [
            format_timestamp(reportDate) for reportDate in self.Report_Date
        ]

    def __repr__(self) -> str:

        _format_dates = lambda dates: [date.strftime("%Y-%m-%d") for date in dates]

        result = f"Stock Earnings:\n"
        result += f"Symbol: {self.Symbol}\n"
        result += f"Fiscal Year: {self.Fiscal_Year}\n"
        result += f"Fiscal Quarter: {self.Fiscal_Quarter}\n"
        result += f"Date: {_format_dates(self.Date)}\n"
        result += f"Report Date: {_format_dates(self.Report_Date)}\n"
        result += f"Report Time: {self.Report_Time}\n"
        result += f"Currency: {self.Currency}\n"
        result += f"Reported EPS: {self.Reported_EPS}\n"
        result += f"Estimated EPS: {self.Estimated_EPS}\n"
        result += f"Surprise EPS: {self.Surprise_EPS}\n"
        result += f"Surprise EPS Percent: {self.Surprise_EPS_Percent}\n"
        result += f"Updated: {_format_dates(self.Updated)}\n"
        return result

    def __str__(self) -> str:
        return self.__repr__()

    @classmethod
    def from_dict(cls, data: dict) -> "StockEarningsHumanReadable":
        data["Surprise_EPS_Percent"] = data["Surprise EPS %"]
        data.pop("Surprise EPS %")
        data = {k.replace(" ", "_"): v for k, v in data.items()}
        return cls(**data)
