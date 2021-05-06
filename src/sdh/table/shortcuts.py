from django.shortcuts import _get_queryset


def get_object_or_none(klass, *args, **kwargs):
    queryset = _get_queryset(klass)
    try:
        return queryset.get(*args, **kwargs)
    except queryset.model.DoesNotExist:
        return None


def atoi(value, default=None):
    try:
        rc = int(value)
    except (ValueError, TypeError):
        rc = default
    return rc


def fn_value(method_or_property):
    if callable(method_or_property):
        return method_or_property()
    return method_or_property


