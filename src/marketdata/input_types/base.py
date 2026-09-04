import datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from marketdata.exceptions import MinMaxDateValidationError, MinMaxValueValidationError
from marketdata.utils import check_is_date

BaseModelConfig = ConfigDict(populate_by_name=True, frozen=False)

# Where CSV output lands when the caller gives no filename: relative to the
# working directory, created only when a file is written.
DEFAULT_CSV_DIR = Path("output")


class BaseInputType(BaseModel):
    def _validate_min_max_dates(
        self, min_param: str | None, max_param: str | None
    ) -> None:
        min_value = getattr(self, min_param)
        max_value = getattr(self, max_param)

        min_is_date = check_is_date(min_value)
        max_is_date = check_is_date(max_value)

        if min_is_date and max_is_date:
            if min_value > max_value:
                raise MinMaxDateValidationError(
                    f"{min_param} must be less than {max_param}"
                )

    def _validate_min_max_value(
        self, min_param: str | None, max_param: str | None
    ) -> None:
        min_value = getattr(self, min_param)
        max_value = getattr(self, max_param)

        if min_value is not None and max_value is not None and min_value > max_value:
            raise MinMaxValueValidationError(
                f"{min_param} must be less than or equal to {max_param}"
            )


class OutputFormat(str, Enum):
    DATAFRAME = "dataframe"
    INTERNAL = "internal"
    JSON = "json"
    CSV = "csv"


class DateFormat(str, Enum):
    TIMESTAMP = "timestamp"
    UNIX = "unix"
    SPREADSHEET = "spreadsheet"


class Mode(str, Enum):
    LIVE = "live"
    CACHED = "cached"
    DELAYED = "delayed"


class UserUniversalAPIParams(BaseInputType):

    model_config = BaseModelConfig

    output_format: OutputFormat = Field(
        default=OutputFormat.DATAFRAME, description="The output format to use"
    )
    date_format: DateFormat | None = Field(
        default=None,
        description="The date format to use",
        alias="dateformat",
    )
    columns: list[str] | None = Field(default=None, description="The columns to use")
    add_headers: bool | None = Field(
        default=None, description="Whether to add headers", alias="headers"
    )
    use_human_readable: bool | None = Field(
        default=None, description="Whether to use human readable", alias="human"
    )
    mode: Mode | None = Field(default=None, description="The mode to use")
    filename: str | Path | None = Field(default=None, description="The filename to use")

    @property
    def api_format(self) -> str:
        if self.output_format in [OutputFormat.DATAFRAME, OutputFormat.INTERNAL]:
            return OutputFormat.JSON.value
        return (
            self.output_format.value
            if self.output_format is not None
            else OutputFormat.JSON.value
        )

    @field_validator("filename")
    def validate_filename(cls, file_path: str | Path | None) -> Path:
        """Resolve and sanity-check the CSV target without touching the filesystem.

        Validation runs on every request, whatever the output format, so it must
        stay free of side effects: the ``output/`` directory is created by
        ``write_file`` when a file is actually written (#43). The checks below
        are an early courtesy for caller-supplied names; the authoritative
        "must not exist" guarantee is the exclusive create in ``write_file``.
        """
        if file_path is None:
            return DEFAULT_CSV_DIR / (
                f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.csv"
            )

        if isinstance(file_path, str):
            file_path = Path(file_path)

        if file_path.is_dir():
            raise ValueError(f"Filename is a directory: {file_path}")
        if not str(file_path).endswith(".csv"):
            raise ValueError(f"Filename must end with .csv: {file_path}")
        if file_path.exists():
            raise ValueError(f"Filename already exists: {file_path}")
        if not file_path.parent.exists():
            raise ValueError(f"Filename directory does not exist: {file_path}")

        return file_path

    def write_file(self, content: str) -> str:
        """Write ``content`` to ``filename`` and return the absolute path.

        The file is created exclusively (``O_CREAT | O_EXCL``): if the path
        appeared, or was symlinked, between validation and this write, the call
        fails with ``FileExistsError`` instead of silently overwriting (#43).
        ``newline=""`` keeps the CSV bytes exactly as received on every platform.
        """
        self.filename.parent.mkdir(parents=True, exist_ok=True)
        with self.filename.open("x", encoding="utf-8", newline="") as handle:
            handle.write(content)
        return str(self.filename.absolute())
