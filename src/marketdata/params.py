import inspect
from functools import wraps
from typing import Callable

from marketdata.exceptions import KeywordOnlyArgumentError
from marketdata.input_types.base import BaseInputType, UserUniversalAPIParams
from marketdata.internal_settings import ALLOWED_POSITIONAL_PARAMS


def _validate_function_signature(func: Callable) -> None:
    signature = inspect.signature(func)
    params = list(signature.parameters.values())

    first = params[0]
    if first.name != "self" or first.kind != inspect.Parameter.POSITIONAL_OR_KEYWORD:
        raise ValueError(
            f"Function {func.__name__} must have 'self' as the first positional argument"
        )

    user_universal_params = next(
        (param for param in params if param.name == "user_universal_params"), None
    )
    if user_universal_params is None:
        raise ValueError(
            f"Function {func.__name__} must have a 'user_universal_params' argument"
        )

    input_params = next(
        (param for param in params if param.name == "input_params"), None
    )
    if input_params is None:
        raise ValueError(
            f"Function {func.__name__} must have a 'input_params' argument"
        )


def _get_positional_param(func: Callable) -> inspect.Parameter | None:
    parameters = inspect.signature(func).parameters
    for param in ALLOWED_POSITIONAL_PARAMS:
        if param in parameters:
            return parameters[param]
    return None


def universal_params(func: Callable = None, resource_input_type: BaseInputType = None):

    if func is None:
        return lambda f: universal_params(f, resource_input_type=resource_input_type)

    _validate_function_signature(func)

    @wraps(func, assigned=("__module__", "__name__", "__qualname__", "__doc__"))
    def wrapper(*args, **kwargs):

        func_param = _get_positional_param(func)
        if func_param:
            func_param_arg_value = args[1] if len(args) > 1 else None
            func_param_kwargs_value = kwargs.get(func_param.name)
            kwargs[func_param.name] = func_param_arg_value or func_param_kwargs_value

        if "user_universal_params" in kwargs:
            user_universal_params = kwargs.pop("user_universal_params")
        else:
            user_universal_params = UserUniversalAPIParams.model_validate(kwargs)

        if "input_params" in kwargs:
            input_params = kwargs.pop("input_params")
        else:
            input_params = resource_input_type.model_validate(kwargs)

        input_kwargs = {
            key: value
            for key, value in kwargs.items()
            if key not in UserUniversalAPIParams.model_fields
            and key not in ("user_universal_params", "input_params")
        }
        func_args = [
            param
            for param in inspect.signature(func).parameters.values()
            if param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
        ]
        if not len(args) <= len(func_args):

            def _get_param_example(param: inspect.Parameter) -> str:
                return f"{param.name}={param.annotation}"

            def _get_param_examples(params: list[inspect.Parameter]) -> str:
                return ", ".join(
                    [
                        _get_param_example(param)
                        for param in params
                        if param.name != "self"
                    ]
                )

            param_names = ", ".join(
                [param.name for param in func_args if param.name != "self"]
            )
            raise KeywordOnlyArgumentError(
                f"Only '{param_names}' can be passed as a positional argument to {func.__name__}. "
                f"All other arguments must be keyword-only. "
                f"Good Example: {func.__name__}({_get_param_examples(func_args)}) or "
                f"""Bad Example: {func.__name__}("some positional argument", "another positional argument")"""
            )

        return func(
            args[0],
            **input_kwargs,
            user_universal_params=user_universal_params,
            input_params=input_params,
        )

    excluded_params = [
        "self",
        "args",
        "kwargs",
        "user_universal_params",
        "input_params",
    ]
    excluded_params.extend(ALLOWED_POSITIONAL_PARAMS)

    input_params_annotations = [
        inspect.Parameter(name, inspect.Parameter.KEYWORD_ONLY, annotation=annotation)
        for name, annotation in resource_input_type.model_fields.items()
        if name not in excluded_params
    ]
    user_universal_params_annotations = [
        inspect.Parameter(name, inspect.Parameter.KEYWORD_ONLY, annotation=annotation)
        for name, annotation in UserUniversalAPIParams.model_fields.items()
        if name not in excluded_params
    ]

    added_params = input_params_annotations + user_universal_params_annotations

    original_signature = inspect.signature(func)
    wrapper.__signature__ = original_signature.replace(parameters=added_params)
    setattr(wrapper, "_input_model", resource_input_type)

    return wrapper
