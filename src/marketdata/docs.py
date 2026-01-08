import inspect
from typing import Annotated, Any, Callable, Union, get_args, get_origin, get_type_hints


def _get_annotation_data(annotation: Any) -> str:
    if annotation is inspect._empty:
        return None

    origin = get_origin(annotation)

    if origin is Annotated:
        real_type, *metadata = get_args(annotation)
        desc = metadata[0] if metadata else None
        type_str = _get_annotation_data(real_type)
        return f"{type_str}  # {desc}"

    if origin is Union:
        args = get_args(annotation)
        return f" | ".join([_get_annotation_data(arg) for arg in args])

    if origin is list:
        args = get_args(annotation)
        return f"list[{_get_annotation_data(args[0])}]"

    if hasattr(annotation, "__name__"):
        return annotation.__name__

    return str(annotation)


def _get_func_info(func: Callable, exclude_params: list[str] = None) -> dict:
    signature = inspect.signature(func)
    hints = get_type_hints(func, include_extras=True)

    docs_info = {
        "name": func.__name__,
        "doc": inspect.getdoc(func),
        "params": [],
        "return": None,
    }
    for name, param in signature.parameters.items():
        if name in ["self", "args", "kwargs"] or (
            exclude_params and name in exclude_params
        ):
            continue

        annotation = hints.get(name, None) or param.annotation
        docs_info["params"].append(
            {
                "name": name,
                "type": _get_annotation_data(annotation),
                "default": None if param.default is inspect._empty else param.default,
                "kind": param.kind.name,
            }
        )

    if signature.return_annotation is not inspect._empty:
        docs_info["return"] = _get_annotation_data(signature.return_annotation)

    return docs_info


def _get_docstring_from_func_info(data: dict) -> str:

    docstring = "#" * 80 + "\n"
    docstring += f"Method name: {data['name']}\n\n"
    if data["doc"]:
        docstring += f"{data['doc']}\n\n"
    if data["params"]:
        docstring += "## Parameters\n\n"
        for param in data["params"]:
            description = param.get("description", "")
            docstring += f"- {param['name']} ({param['type']}): {description}\n"
    if data["return"]:
        docstring += "#" * 80 + "\n\n"
        docstring += "## Returns\n\n"
        docstring += f"- {data['return']}\n"

    return docstring


def docs(func: Callable = None, *, exclude_params: list[str] = None):
    if func is None:
        return lambda f: docs(f, exclude_params=exclude_params)

    inner = getattr(func, "__wrapped__", None)

    inner_docs_info = _get_func_info(inner, exclude_params) if inner else {}
    docs_info = _get_func_info(func, exclude_params)

    combined_docs_info = inner_docs_info
    combined_docs_info["params"].extend(docs_info["params"])
    combined_docs_info["return"] = docs_info["return"]

    func.__docs__ = _get_docstring_from_func_info(combined_docs_info)

    return func
