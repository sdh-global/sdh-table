import re
import django
from django.shortcuts import _get_queryset
from django.template.loader import render_to_string as django_render_to_string
from django.template import RequestContext


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


def render_to_string(template, context, request):
    if re.match('^1\.5\..*', django.get_version()):
        #  RequestContext should be used for Django 1.5 backward compatibility
        return django_render_to_string(template, RequestContext(request, context))
    else:
        return django_render_to_string(template, context, request=request)

