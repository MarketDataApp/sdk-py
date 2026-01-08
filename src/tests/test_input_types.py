import datetime
from pathlib import Path

import pytest
from pydantic import Field, model_validator

from marketdata.exceptions import MinMaxDateValidationError
from marketdata.input_types.base import (
    BaseInputType,
    OutputFormat,
    UserUniversalAPIParams,
)


class DummyInput(BaseInputType):
    min_param: datetime.date | str = Field(default="2025-01-01")
    max_param: datetime.date | str = Field(default="2025-01-01")

    @model_validator(mode="after")
    def validate_input(self) -> "DummyInput":
        self._validate_min_max_dates("min_param", "max_param")
        return self


def test_base_input_type_min_max_validation():
    with pytest.raises(MinMaxDateValidationError):
        DummyInput(min_param="2025-01-01", max_param="2024-01-01")


def test_universal_api_params_api_format():
    params = UserUniversalAPIParams(output_format=OutputFormat.DATAFRAME)
    assert params.api_format == OutputFormat.JSON

    params = UserUniversalAPIParams(output_format=OutputFormat.JSON)
    assert params.api_format == OutputFormat.JSON

    params = UserUniversalAPIParams(output_format=OutputFormat.CSV)
    assert params.api_format == OutputFormat.CSV

    params = UserUniversalAPIParams(output_format=OutputFormat.INTERNAL)
    assert params.api_format == OutputFormat.JSON


def test_universal_api_params_filename(tmp_path: Path):

    params = UserUniversalAPIParams(filename=tmp_path / "test.csv")
    assert params.filename == tmp_path / "test.csv"

    params = UserUniversalAPIParams(filename=str(tmp_path / "test.csv"))
    assert params.filename == tmp_path / "test.csv"

    params = UserUniversalAPIParams(filename=None)
    assert isinstance(params.filename, Path)
    assert params.filename.parent.exists()
    assert params.filename.parent.is_dir()
    assert params.filename.suffix == ".csv"

    with pytest.raises(ValueError):
        UserUniversalAPIParams(filename="test.txt")

    with pytest.raises(ValueError):
        UserUniversalAPIParams(filename=tmp_path / "test.txt")

    with pytest.raises(ValueError):
        UserUniversalAPIParams(filename=tmp_path / "test")

    with pytest.raises(ValueError):
        UserUniversalAPIParams(filename=tmp_path / "test/test.csv")

    existing_file = tmp_path / "test.csv"
    existing_file.touch()
    with pytest.raises(ValueError):
        UserUniversalAPIParams(filename=existing_file)

    directory = tmp_path / "test"
    directory.mkdir()
    with pytest.raises(ValueError):
        UserUniversalAPIParams(filename=directory)
