import logging
from dataclasses import fields, is_dataclass
from typing import Any

from marketdata.utils import column_key

# By name, not `get_logger()`: importing the package must not attach a handler.
_logger = logging.getLogger("marketdata.logger")

_EXTRA_ATTRIBUTE = "_marketdata_extra"


def get_extra(model: Any) -> dict[str, Any]:
    """Read the columns of an API answer that the model built from it does not
    declare.

    Args:
        model: A model a resource call returned on ``OutputFormat.INTERNAL``,
            one row of a list result, or a model built with ``from_dict``.

    Returns:
        Each such column, named as the API sent it, with its value as the
        model's answer was decoded: a number with a fraction is a ``Decimal``
        on the resources that decode money exactly. A single-object model
        holds the whole column, a row its own value. Empty when there is none.
    """
    namespace = getattr(model, "__dict__", None)
    if not isinstance(namespace, dict):
        return {}
    return dict(namespace.get(_EXTRA_ATTRIBUTE, {}))


def _with_extra(model: Any, extra: dict[str, Any]) -> Any:
    """Keep the undeclared columns of an answer on the model built from it.

    Args:
        model: The model built from the answer.
        extra: The columns the model does not declare, keyed as the API sent
            them.

    Returns:
        ``model``, which ``get_extra`` reads ``extra`` from.
    """
    if extra:
        model.__dict__[_EXTRA_ATTRIBUTE] = extra
    return model


def _with_row_extra(models: list[Any], extra: dict[str, Any]) -> list[Any]:
    """Keep the undeclared columns of a column-oriented answer on its rows.

    Args:
        models: The models built from the answer's rows, in row order.
        extra: The columns the model does not declare, keyed as the API sent
            them.

    Returns:
        ``models``. A column that is a list as long as the rows gives each row
        its own value; any other value goes to every row as the API sent it.
    """
    for index, model in enumerate(models):
        _with_extra(
            model,
            {
                key: (
                    value[index]
                    if isinstance(value, list) and len(value) == len(models)
                    else value
                )
                for key, value in extra.items()
            },
        )
    return models


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


def _split_fields(output_model: type, data: Any) -> tuple[Any, dict[str, Any]]:
    """Split an API answer into the fields of the output model it is built into
    and the columns the model does not declare.

    Args:
        output_model: The output model dataclass the answer is built into.
        data: The answer, keyed by column name.

    Returns:
        The values of the keys that name a column or a field of the model,
        keyed by field name, and every other key but the status flag ``s``
        with its value, as the API sent them. Those are logged at DEBUG, once
        per answer. An answer that is not an object, or that carries none of
        the model's columns, comes back as it is with no other key, for the
        model to refuse.
    """
    columns = _column_names(output_model)
    if not isinstance(data, dict) or not any(key in data for key in columns.values()):
        return data, {}
    by_key = {field.name: field.name for field in fields(output_model)}
    by_key.update({column: name for name, column in columns.items()})
    extra = {
        key: value for key, value in data.items() if key not in by_key and key != "s"
    }
    if extra:
        _logger.debug(
            f"The API sent the columns {list(extra)!r}, which"
            f" {output_model.__name__} does not declare; get_extra() holds them"
        )
    return {by_key[key]: value for key, value in data.items() if key in by_key}, extra


def _to_fields(output_model: type, data: Any) -> Any:
    """Key an API answer that carries only declared columns by the fields of
    the output model it is built into.

    Args:
        output_model: The output model dataclass the answer is built into.
        data: The answer, keyed by column name.

    Returns:
        The fields ``_split_fields`` returns.
    """
    return _split_fields(output_model, data)[0]


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
