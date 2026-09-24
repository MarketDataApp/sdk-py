from dataclasses import fields, is_dataclass
from typing import Any

from marketdata.utils import column_key


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


def _to_fields(output_model: type, data: dict) -> dict:
    """Rename the keys of an API answer from column names to field names.

    Args:
        output_model: The output model the answer is built into.
        data: The answer, keyed by column name.

    Returns:
        The same values keyed by field name. A key that names no column is
        kept as it is.
    """
    by_column = {column: name for name, column in _column_names(output_model).items()}
    return {by_column.get(key, key): value for key, value in data.items()}


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
