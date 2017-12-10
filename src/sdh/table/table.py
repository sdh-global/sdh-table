from __future__ import unicode_literals

from copy import deepcopy
import csv
import re
from collections import OrderedDict

from django.utils import six
from django.db.models import Q
from django.utils.html import strip_tags

from . import widgets


def get_declared_fields(bases, attrs, with_base_columns=True):
    """
    Create a list of form field instances from the passed in 'attrs', plus any
    similar fields on the base classes (in 'bases'). This is used by both the
    Form and ModelForm metclasses.

    If 'with_base_fields' is True, all fields from the bases are used.
    Otherwise, only fields in the 'declared_fields' attribute on the bases are
    used. The distinction is useful in ModelForm subclassing.
    Also integrates any additional media definitions
    """
    # FIXME: refactoring required for this method to use modern metaclass build approach
    columns = [(column_name, obj) for column_name, obj in attrs.items() if
               isinstance(obj, widgets.BaseWidget)]
    columns.sort(key=lambda item: item[1].creation_counter)

    for column_name, obj in columns:
        attrs.pop(column_name)

    return OrderedDict(columns)


class DeclarativeFieldsMetaclass(type):
    """
    Metaclass that converts Field attributes to a dictionary called
    'base_fields', taking into account parent class 'base_fields' as well.
    """

    def __new__(mcs, name, bases, attrs):
        attrs['base_columns'] = get_declared_fields(bases, attrs)

        attr_meta = attrs.pop('Meta', None)

        permanent = ()
        sortable = ()
        filter_form = None
        search = ()
        use_keyboard = False
        global_profile = False
        template = "sdh/table/table_body.html"
        template_body_content = "sdh/table/table_body_content.html"
        template_paginator = "sdh/table/table_paginator.html"
        reload_interval = None
        csv_allow = False
        csv_dialect = csv.excel
        title = None

        if attr_meta:
            permanent = getattr(attr_meta, 'permanent', ())
            sortable = getattr(attr_meta, 'sortable', ())
            filter_form = getattr(attr_meta, 'filter_form', None)
            search = getattr(attr_meta, 'search', None)
            use_keyboard = getattr(attr_meta, 'use_keyboard', False)
            reload_interval = getattr(attr_meta, 'reload_interval', None)
            global_profile = getattr(attr_meta, 'global_profile', False)
            template = getattr(attr_meta, 'template', template)
            template_body_content = getattr(attr_meta, 'template_body_content', template_body_content)
            template_paginator = getattr(attr_meta, 'template_paginator', template_paginator)
            csv_allow = getattr(attr_meta, 'csv_allow', False)
            title = getattr(attr_meta, 'title', None)
            csv_dialect = getattr(attr_meta, 'csv_dialect', csv.excel)

        attrs['permanent'] = permanent
        attrs['sortable'] = sortable
        attrs['filter_form'] = filter_form
        attrs['search'] = search
        attrs['use_keyboard'] = use_keyboard
        attrs['global_profile'] = global_profile
        attrs['template'] = template
        attrs['template_body_content'] = template_body_content
        attrs['template_paginator'] = template_paginator
        attrs['reload_interval'] = reload_interval
        attrs['csv_allow'] = csv_allow
        attrs['csv_dialect'] = csv_dialect
        attrs['title'] = title

        new_class = super(DeclarativeFieldsMetaclass, mcs).__new__(mcs, name, bases, attrs)

        return new_class


class BaseTableView(object):
    def __init__(self, ref_id, **kwargs):
        self.columns = deepcopy(self.base_columns)
        self.id = ref_id
        self.kwargs = kwargs

    def get_id(self):
        return self.id

    def get_row_class(self, controller, row):
        return ''

    def apply_filter(self, filter, source):
        pass

    def apply_search(self, search_value, source):
        if not search_value:
            return
        search_filter = []
        for orm_field_name in self.search:
            filter_name = "%s__icontains" % orm_field_name
            search_filter.append(Q(**{filter_name: search_value}))

        if search_filter:
            result_q = Q()
            for item in search_filter:
                result_q.add(item, Q.OR)
            source.filter(result_q)


class CellTitle(object):
    def __init__(self, controller, key, column):
        self.controller = controller
        self.key = key
        self.column = column

    def is_sortable(self):
        return self.key in self.controller.table.sortable

    def is_sorted(self):
        return self.key == self.controller.sort_by

    def is_asc(self):
        return self.key == self.controller.sort_by and self.controller.sort_asc

    def html_title(self):
        return self.column.html_title()

    def html_title_attr(self):
        return self.column.html_title_attr()

    def is_permanent(self):
        return self.key in self.controller.table.permanent

    def is_visible(self):
        return self.key in self.controller.visible_columns


class BoundCell(object):
    def __init__(self, row_index, key, bound_row, column):
        self.row_index = row_index
        self.bound_row = bound_row
        self.key = key
        self.column = column
        self.row_index = row_index

    def get_cell_class(self):
        if hasattr(self.bound_row.controller.table, 'cell_class_%s' % self.key):
            cb = getattr(self.bound_row.controller.table, 'cell_class_%s' % self.key)
            return cb(self.bound_row.controller.table, self.row_index, self.bound_row.row,
                      self.column.get_value(self.bound_row.row))
        return ''

    def get_cell_style(self):
        if hasattr(self.bound_row.controller.table, 'cell_style_%s' % self.key):
            cb = getattr(self.bound_row.controller.table, 'cell_style_%s' % self.key)
            return cb(self.bound_row.controller.table, self.row_index, self.bound_row.row,
                      self.column.get_value(self.bound_row.row))
        return ''

    def as_html(self):
        if hasattr(self.bound_row.controller.table, 'render_%s' % self.key):
            cb = getattr(self.bound_row.controller.table, 'render_%s' % self.key)
            return cb(self.bound_row.controller.table, self.row_index, self.bound_row.row,
                      self.column.get_value(self.bound_row.row))

        return self.column.html_cell(self.row_index, self.bound_row.row, request=self.bound_row.controller.request)

    def as_csv(self):
        cb = getattr(self.bound_row.controller.table, 'render_csv_%s' % self.key, None)
        if cb and callable(cb):
            return cb(self.bound_row.controller.table,
                      self.row_index,
                      self.bound_row.row,
                      self.column.get_value(self.bound_row.row))

        default_value = re.sub(r'\n\r|\r\n|\r|\n',
                               ' ',
                               str(strip_tags(self.as_html().replace('&nbsp;', ' '))))
        return default_value

    def html_cell_attr(self):
        return self.column.html_cell_attr()

    def get_id(self):
        return self.key


class BoundRow(object):
    def __init__(self, controller, row_index, row):
        self.controller = controller
        self.row = row
        self.row_index = row_index

    def __iter__(self):
        for key, column in self.controller.iter_columns():
            yield BoundCell(self.row_index, key, self, column)

    def get_id(self):
        table_id = self.controller.table.get_id() or 'table'

        return "%s_row_%d" % (table_id, self.row_index)

    def get_row_class(self):
        return self.controller.table.get_row_class(self.controller, self.row)


class TableView(six.with_metaclass(DeclarativeFieldsMetaclass, BaseTableView)):
    """ Table view class """
