import logging
from dataclasses import fields, is_dataclass
from typing import Any

from marketdata.utils import column_key

# By name, not `get_logger()`: importing the package must not attach a handler.
logger = logging.getLogger("marketdata.logger")


def _column_names(output_model: type) -> dict[str, str]:
    """Map each field of an output model to the name of its column in the API's
    answers.

    A human-readable model (one with an ``api_model`` twin) spells a field with
    spaces for its underscores, unless its ``api_names`` mapping names the
    column. Any other model uses the field name.

    Args:
        output_model: An output model.

    Returns:
        The column name of every field but the status flag ``s``, in field
        order. Empty for a class that is not a dataclass.
    """
    if not is_dataclass(output_model):
        return {}
    renamed = getattr(output_model, "api_names", {})
    human = hasattr(output_model, "api_model")
    return {
        field.name: renamed.get(
            field.name, field.name.replace("_", " ") if human else field.name
        )
        for field in fields(output_model)
        if field.name != "s"
    }


def _column_types(output_model: type) -> dict[str, Any]:
    """Map each column of an output model to its field annotation.

    Args:
        output_model: An output model.

    Returns:
        The annotation of each column, keyed by column name, in field order.
        Empty for a class that is not a dataclass.
    """
    if not is_dataclass(output_model):
        return {}
    names = _column_names(output_model)
    return {
        names[field.name]: field.type
        for field in fields(output_model)
        if field.name in names
    }


def _to_fields(output_model: type, data: Any) -> Any:
    """Key an API answer by the fields of the output model it is built into.

    Args:
        output_model: The output model dataclass the answer is built into.
        data: The answer, keyed by column name.

    Returns:
        The values of the keys that name a column or a field of the model,
        keyed by field name. Any other key is left out and logged at DEBUG,
        except the status flag ``s``. An answer that is not an object, or that
        carries none of the model's columns, comes back as it is, for the
        model to refuse.
    """
    columns = _column_names(output_model)
    if not isinstance(data, dict) or not any(key in data for key in columns.values()):
        return data
    by_key = {field.name: field.name for field in fields(output_model)}
    by_key.update({column: name for name, column in columns.items()})
    undeclared = [key for key in data if key not in by_key and key != "s"]
    if undeclared:
        logger.debug(
            f"The API sent the columns {undeclared!r}, which"
            f" {output_model.__name__} does not declare; they are left out"
        )
    return {by_key[key]: value for key, value in data.items() if key in by_key}


def _model_columns(output_model: type, requested: list[str] | None = None) -> list[str]:
    """List the columns a result of an output model carries.

    Args:
        output_model: An output model dataclass.
        requested: The ``columns=`` filter. A name matches a column case- and
            space-insensitively by its column name, its field name or, on a
            human-readable model, the API name at the same position of its
            ``api_model`` twin. The API's own aliases (``open`` for ``o``) are
            not matched.

    Returns:
        Every column name in field order or, under a filter, the matched ones
        in request order without duplicates. The full list when no name
        matches.

    Raises:
        ValueError: If a human-readable model and its ``api_model`` twin have
            different column counts.
    """
    names = _column_names(output_model)
    columns = list(names.values())
    if not requested:
        return columns
    by_key: dict[str, str] = {}
    for name, column in names.items():
        by_key.setdefault(column_key(column), column)
        by_key.setdefault(column_key(name), column)
    api_model = getattr(output_model, "api_model", None)
    if api_model is not None:
        # A column's own name wins over the position: MarketStatusHumanReadable
        # is not in its twin's order.
        for api_name, column in zip(_column_names(api_model), columns, strict=True):
            by_key.setdefault(column_key(api_name), column)
    selected: list[str] = []
    for name in requested:
        match = by_key.get(column_key(name))
        if match is not None and match not in selected:
            selected.append(match)
    return selected or columns
