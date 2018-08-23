from __future__ import unicode_literals

from django.core.urlresolvers import reverse, NoReverseMatch
from django.db.models.manager import Manager
from django.utils import timezone
from django.utils import formats
from django.utils.encoding import force_text
from django.conf import settings
from django.utils.safestring import mark_safe
from django.template.loader import render_to_string


class BaseWidget(object):
    creation_counter = 0

    def __init__(self, label, refname=None, width=None, title_attr=None, cell_attr=None):
        self.label = label
        self.refname = refname
        self.title_attr = title_attr
        self.cell_attr = cell_attr
        self.width = width

        # Increase the creation counter, and save our local copy.
        self.creation_counter = BaseWidget.creation_counter
        BaseWidget.creation_counter += 1

    def html_title(self):
        return self.label

    def _recursive_value(self, row, keylist):
        value = None
        if hasattr(row, keylist[0]):
            value = getattr(row, keylist[0])
            if callable(value):
                value = value()
            if len(keylist) > 1:
                return self._recursive_value(value, keylist[1:])

        return value

    def get_value(self, row, refname=None, default=None):
        if refname is None and self.refname is None:
            return default

        value = self._recursive_value(row, (refname or self.refname).split('__'))
        if value is not None:
            if isinstance(value, Manager):
                return value.all()

            return value
        return default

    def html_cell(self, row_index, row, **kwargs):
        value = self.get_value(row)
        if value is None:
            value = '&nbsp;'
        return mark_safe(value)

    def _dict2attr(self, attr):
        if not attr:
            return ""

        rc = ""
        for key, value in attr.items():
            rc += ' %s="%s"' % (key, value)

        return mark_safe(rc)

    def html_title_attr(self):
        return self._dict2attr(self.title_attr)

    def html_cell_attr(self):
        return self._dict2attr(self.cell_attr)


class LabelWidget(BaseWidget):
    pass


class DateTimeWidget(BaseWidget):
    def __init__(self, *kargs, **kwargs):
        self.format = "%d/%m/%y %H:%M"

        _kwargs = {}
        for key, value in kwargs.items():
            if key == 'format':
                self.format = value
            else:
                _kwargs[key] = value

        super(DateTimeWidget, self).__init__(*kargs, **_kwargs)

    def html_cell(self, row_index, row, **kwarg):
        value = self.get_value(row)
        if value:
            return value.strftime(self.format)
        return mark_safe('&nbsp;')


class LocalDateTimeWidget(BaseWidget):
    def html_cell(self, row_index, row, **kwargs):
        value = self.get_value(row)
        if value:
            tz = timezone.get_current_timezone()
            value = value.astimezone(tz)
            return force_text(formats.localize(value, use_l10n=settings.USE_L10N))
        return mark_safe('&nbsp;')


class HrefWidget(BaseWidget):
    def __init__(self, *kargs, **kwargs):
        self.href = None
        self.reverse = None
        self.reverse_column = 'id'
        my_kwargs = {}

        for key, value in kwargs.items():
            if key == 'href':
                self.href = value
            elif key == 'reverse':
                self.reverse = value
            elif key == 'reverse_column':
                self.reverse_column = value
            else:
                my_kwargs[key] = value

        super(HrefWidget, self).__init__(*kargs, **my_kwargs)

    def html_cell(self, row_index, row, **kwargs):
        href = ''
        value = self.get_value(row, default='&nbsp;')

        if self.reverse:
            try:
                href = reverse(self.reverse, args=[self.get_value(row, self.reverse_column), ])
            except NoReverseMatch:
                href = "#NoReverseMatch"

        return mark_safe("<a href='%s'>%s</a>" % (href, value))


class ConditionHrefWidget(HrefWidget):
    """
    HrefWidget for table field which render
    field with href to view if condition lambda is True and acl result is True, otherwise the value only.
    Condition example:
    either
        condition=lambda row, request: row.some_method()
    or
        acl='is_access_view'
    """
    def __init__(self, *args, **kwargs):
        self.condition = kwargs.pop('condition', None)
        self.acl = kwargs.pop('acl', None)
        super(ConditionHrefWidget, self).__init__(*args, **kwargs)

    def html_cell(self, row_index, row, **kwargs):
        _request = kwargs.pop('request', None)
        is_href = True
        href = ''
        value = self.get_value(row, default='&nbsp;')

        if self.condition and callable(self.condition):
            is_href &= bool(self.condition(row, _request))

        if self.acl and hasattr(_request, 'acl'):
            is_href &= bool(getattr(_request.acl, self.acl))

        if self.reverse:
            try:
                href = reverse(self.reverse, args=[self.get_value(row, self.reverse_column), ])
            except NoReverseMatch:
                href = "#NoReverseMatch"

        if is_href:
            return mark_safe("<a href='%s'>%s</a>" % (href, value))
        return mark_safe(value)


class TemplateWidget(BaseWidget):
    def __init__(self, *args, **kwargs):
        self.template = kwargs.pop('template', None)
        self.request = kwargs.pop('request', None)
        super(TemplateWidget, self).__init__(*args, **kwargs)

    def html_cell(self, row_index, row, **kwargs):
        request = kwargs.pop('request', None)
        value = self.get_value(row, default=None)
        return mark_safe(render_to_string(self.template,
                                          {'item': row,
                                           'value': value,
                                           'index': row_index,
                                           'request': request}))
