import inspect
from enum import Enum
from typing import Annotated, Union

from marketdata.docs import (
    _get_annotation_data,
    _get_docstring_from_func_info,
    _get_func_info,
)


def test_get_annotation_data():
    assert _get_annotation_data(int) == "int"
    assert _get_annotation_data(float) == "float"
    assert _get_annotation_data(str) == "str"
    assert _get_annotation_data(bool) == "bool"
    assert _get_annotation_data(list[int]) == "list[int]"
    assert _get_annotation_data(list[str]) == "list[str]"
    assert _get_annotation_data(list[bool]) == "list[bool]"
    assert _get_annotation_data(list[float]) == "list[float]"
    assert _get_annotation_data(list[int]) == "list[int]"
    assert _get_annotation_data(Union[int, None]) == "int | NoneType"
    assert (
        _get_annotation_data(Annotated[Union[int, str], "test"]) == "int | str  # test"
    )
    assert _get_annotation_data(inspect._empty) is None

    def test_func(a: Annotated[int, "test"]):
        return a

    info = _get_func_info(test_func)
    assert info["params"][0]["type"] == "int  # test"

    def test_origin_union(a: Annotated[int | str, "test"]):
        return a

    info = _get_func_info(test_origin_union)
    assert info["params"][0]["type"] == "int | str  # test"

    class TestEnum(str, Enum):
        TEST = "test"

    def test_origin_enum(a: TestEnum):
        return a

    info = _get_func_info(test_origin_enum)
    assert info["params"][0]["type"] == "TestEnum"


def test_get_func_info():
    def test_func(a: int, b: str, c: bool = True):
        return a, b, c

    info = _get_func_info(test_func)
    assert info["name"] == "test_func"
    assert info["doc"] is None
    assert len(info["params"]) == 3
    assert info["params"][0]["name"] == "a"
    assert info["params"][0]["type"] == "int"
    assert info["params"][0]["default"] is None
    assert info["params"][0]["kind"] == "POSITIONAL_OR_KEYWORD"
    assert info["params"][1]["name"] == "b"
    assert info["params"][1]["type"] == "str"
    assert info["params"][1]["default"] is None
    assert info["params"][1]["kind"] == "POSITIONAL_OR_KEYWORD"
    assert info["params"][2]["name"] == "c"
    assert info["params"][2]["type"] == "bool"
    assert info["params"][2]["default"] is True
    assert info["params"][2]["kind"] == "POSITIONAL_OR_KEYWORD"
    assert info["return"] is None


def test_get_docstring_from_func_info():
    def test_func(a: int, b: str, c: bool = True):
        return a, b, c

    info = _get_func_info(test_func)
    docstring = _get_docstring_from_func_info(info)
    expected_docstring = (
        "#" * 80
        + "\nMethod name: test_func\n\n## Parameters\n\n- a (int): \n- b (str): \n- c (bool): \n"
    )
    assert docstring == expected_docstring
