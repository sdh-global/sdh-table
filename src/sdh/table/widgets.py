import datetime
from django.utils import formats, timezone
from django.utils.formats import date_format
from django.utils.safestring import mark_safe
from django.utils.html import escape

from django.db.models.manager import Manager
from django.db.models.constants import LOOKUP_SEP
from django.template.loader import render_to_string
from django.urls import reverse, NoReverseMatch


class BaseWidget:
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
            if isinstance(value, Manager):
                return value
            if callable(value):
                value = value()
            if len(keylist) > 1:
                return self._recursive_value(value, keylist[1:])
        return value

    def get_value(self, row, refname=None, default=None):
        if refname is None and self.refname is None:
            return default
        value = self._recursive_value(row, (refname or self.refname).split(LOOKUP_SEP))
        if value is not None:
            if isinstance(value, Manager):
                return value.all()
            return value
        return default

    def html_cell(self, row_index, row, **kwargs):
        value = self.get_value(row)
        return value or ' '

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
    """
    LabelWidget for table field which renders the field with refname param as column value
    """
    pass


class DateTimeWidget(BaseWidget):
    """
    DateTimeWidget for table field which renders the field with localized datetime as column value
    """
    def __init__(self, label, format=None, **kwargs):
        self.format = format
        super(DateTimeWidget, self).__init__(label, **kwargs)

    def html_cell(self, row_index, row, **kwarg):
        value = self.get_value(row)
        if isinstance(value, datetime.datetime) and not self.format:
            _format = 'DATETIME_FORMAT'
        elif isinstance(value, datetime.date) and not self.format:
            _format = 'DATE_FORMAT'
        else:
            _format = self.format

        if value:
            return formats.date_format(value, _format)
        return ' '


class LocalDateTimeWidget(BaseWidget):
    """
    LocalDateTimeWidget for table field which renders the field with localized datetime as column value
    """
    def __init__(self, *args, format=None, **attrs):
        self.format = format
        super().__init__(*args, **attrs)

    def html_cell(self, row_index, row, **kwargs):
        value = self.get_value(row)
        if value is None:
            return ' '

        if isinstance(value, datetime.datetime) and timezone.is_aware(value):
            value = timezone.make_naive(value)

        if isinstance(value, datetime.datetime) and not self.format:
            _format = 'DATETIME_FORMAT'
        elif isinstance(value, datetime.date) and not self.format:
            _format = 'DATE_FORMAT'
        else:
            _format = self.format

        return date_format(value, _format)


class LocalDateWidget(LocalDateTimeWidget):
    def __init__(self, *args, format=None, **attrs):
        _format = format or 'DATE_FORMAT'
        super().__init__(*args, format=_format, **attrs)


class HrefWidget(BaseWidget):
    """
    HrefWidget for table field which renders field with href to view
    Usage example:
        email = widgets.HrefWidget(_('Email'), refname='email', reverse='user-retrieve', reverse_column='email')
    """
    def __init__(self, label, href=None, reverse=None, reverse_column=None, **kwargs):
        self.href = href
        self.reverse = reverse
        if not reverse_column:
            self.reverse_column = ('id',)
        elif isinstance(reverse_column, str):
            self.reverse_column = (reverse_column,)
        else:
            self.reverse_column = reverse_column
        super(HrefWidget, self).__init__(label, **kwargs)

    def get_url(self, row):
        if self.reverse:
            try:
                return reverse(self.reverse, args=[self.get_value(row, col) for col in self.reverse_column])
            except NoReverseMatch:
                return "#NoReverseMatch"
        return self.href

    @staticmethod
    def render_url(href, value):
        return mark_safe("<a href='%s'>%s</a>" % (href, escape(value)))

    def html_cell(self, row_index, row, **kwargs):
        href = self.get_url(row)
        value = self.get_value(row, default='')
        if href:
            return self.render_url(href, value)
        return value


class ConditionHrefWidget(HrefWidget):
    """
    ConditionHrefWidget for table field which renders
    field with href to view if condition lambda is True and acl result is True, otherwise the value only.
    Condition example:
    either
        condition=lambda row, request: row.some_method()
    or
        acl='is_access_view'
    """
    def __init__(self, label, condition=None, acl=None, **kwargs):
        super(ConditionHrefWidget, self).__init__(label, **kwargs)
        self.condition = condition
        self.acl = acl

    def html_cell(self, row_index, row, **kwargs):
        _request = kwargs.pop('request', None)
        is_href = True
        href = None
        value = self.get_value(row, default='')
        if self.condition and callable(self.condition):
            is_href &= bool(self.condition(row, _request))
        if self.acl and hasattr(_request, 'acl'):
            is_href &= bool(getattr(_request.acl, self.acl))
        if is_href:
            href = self.get_url(row)
        if href:
            return self.render_url(href, value)
        return value


class TemplateWidget(BaseWidget):
    """
    TemplateWidget for table field which renders field using custom template
    Usage example (django template language):
    in the table:
        actions = widgets.TemplateWidget(_('Actions'), template='some_instance_table_actions_field.html')
    in template:
        <a href="{% url 'some-instance-view' item.id %}" type="button" class="btn">
            <em class="icon-eye"></em>
            {% trans 'View' %}
        </a>
        <a href="{% url 'some-instance-edit' item.id %}" type="button" class="btn">
            <em class="icon-edit"></em>
            {% trans 'Edit' %}
        </a>
    """
    def __init__(self, label, template=None, request=None, **kwargs):
        self.template = template
        self.request = request
        super(TemplateWidget, self).__init__(label, **kwargs)

    def html_cell(self, row_index, row, **kwargs):
        value = self.get_value(row, default=None)
        _request = self.request or kwargs.pop('request', self.request)
        return mark_safe(render_to_string(self.template,
                                          {'item': row,
                                           'value': value,
                                           'row': row,
                                           'index': row_index,
                                           'request': _request}))


class BooleanWidget(TemplateWidget):
    """
    BooleanWidget overrides TemplateWidget using already prepared template
    And you can redefine widget template globally in project
    """
    def __init__(self, label, null=False, template=None, **kwargs):
        template = template or 'sdh/table/widgets/boolean_widget.html'
        super(BooleanWidget, self).__init__(label, template, **kwargs)
        self.null = null

    def html_cell(self, row_index, row, **kwargs):
        value = self.get_value(row, default=None)
        _request = self.request or kwargs.pop('request', self.request)
        return mark_safe(render_to_string(self.template,
                                          {'item': row,
                                           'value': value,
                                           'index': row_index,
                                           'allow_null': self.null,
                                           'request': _request}))
