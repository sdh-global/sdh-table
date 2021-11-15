import re
import csv
import operator
from copy import deepcopy
from functools import reduce
from collections import OrderedDict

from django.db import models
from django.db.models.constants import LOOKUP_SEP
from django.utils.html import strip_tags

from . import widgets

ALL_FIELDS = '__all__'


class DeclarativeFieldsMetaclass(type):
    """
    Metaclass that converts Field attributes to a dictionary called
    'base_fields', taking into account parent class 'base_fields' as well.
    """

    def __new__(cls, name, bases, attrs, **kwargs):
        super_new = super().__new__

        # Collect columns from current class.
        current_columns = []
        for key, value in list(attrs.items()):
            if isinstance(value, widgets.BaseWidget):
                if not value.refname:
                    value.refname = key
                current_columns.append((key, value))
                attrs.pop(key)
        current_columns.sort(key=lambda x: x[1].creation_counter)
        attrs['base_columns'] = OrderedDict(current_columns)

        attr_meta = attrs.pop('Meta', None)

        attrs['permanent'] = getattr(attr_meta, 'permanent', ())
        attrs['default_visible'] = getattr(attr_meta, 'default_visible', ())
        attrs['sortable'] = getattr(attr_meta, 'sortable', ())
        attrs['filter_form'] = getattr(attr_meta, 'filter_form', None)
        attrs['search'] = getattr(attr_meta, 'search', None)
        attrs['use_keyboard'] = getattr(attr_meta, 'use_keyboard', False)
        attrs['reload_interval'] = getattr(attr_meta, 'reload_interval', None)
        attrs['global_profile'] = getattr(attr_meta, 'global_profile', False)
        attrs['paginator_class'] = getattr(attr_meta, 'paginator_class', None)
        attrs['template'] = getattr(attr_meta, 'template', 'sdh/table/table_body.html')
        attrs['template_body_content'] = getattr(attr_meta,
                                                 'template_body_content',
                                                 'sdh/table/table_body_content.html')
        attrs['template_paginator'] = getattr(attr_meta, 'template_paginator', 'sdh/table/table_paginator.html')
        attrs['csv_allow'] = getattr(attr_meta, 'csv_allow', False)
        attrs['csv_dialect'] = getattr(attr_meta, 'csv_dialect', csv.excel)
        attrs['title'] = getattr(attr_meta, 'title', None)

        new_class = super_new(cls, name, bases, attrs, **kwargs)

        return new_class


class TableView(metaclass=DeclarativeFieldsMetaclass):
    lookup_prefixes = {
        '^': 'istartswith',
        '=': 'iexact',
        '@': 'search',  # (Currently only supported Django's MySQL backend.)
        '$': 'iregex',
    }

    def __init__(self, ref_id, **kwargs):
        self.columns = deepcopy(self.base_columns)
        self.id = ref_id
        self.kwargs = kwargs

    def get_id(self):
        return self.id

    def get_row_class(self, controller, row):
        """
        Dummy for further specifying a custom class for each row.
        """
        return ''

    @property
    def get_permanent(self):
        return tuple(self.columns.keys()) if self.permanent == ALL_FIELDS else self.permanent

    @property
    def get_default_visible(self):
        return tuple(self.columns.keys()) if self.default_visible == ALL_FIELDS else self.default_visible

    def apply_filter(self, cleaned_data, source):
        """
        A function that filter results from 'source' using 'cleaned_data' from 'filter_form'.

        Usage example ::

            def apply_filter(self, cleaned_data, source):
                archived_only = cleaned_data.get('archived_only')
                if archived_only:
                    qs.filter(archived=True)

        """
        pass

    def construct_search(self, field_name):
        lookup = self.lookup_prefixes.get(field_name[0])
        if lookup:
            field_name = field_name[1:]
        else:
            lookup = 'icontains'
        return LOOKUP_SEP.join([field_name, lookup])

    def must_call_distinct(self, queryset):
        """
        Return True if 'distinct()' should be used to query the given lookups.
        """
        for search_field in self.search:
            opts = queryset.model._meta
            if search_field[0] in self.lookup_prefixes:
                search_field = search_field[1:]
            parts = search_field.split(LOOKUP_SEP)
            for part in parts:
                field = opts.get_field(part)
                if hasattr(field, 'get_path_info'):
                    # This field is a relation, update opts to follow the relation
                    path_info = field.get_path_info()
                    opts = path_info[-1].to_opts
                    if any(path.m2m for path in path_info):
                        # This field is a m2m relation so we know we need to call distinct
                        return True
        return False

    def apply_search(self, search_value, source):
        if not search_value:
            return
        orm_lookups = [self.construct_search(str(search_field)) for search_field in self.search]
        base = source.qs
        queries = [models.Q(**{orm_lookup: search_value}) for orm_lookup in orm_lookups]
        source.filter(reduce(operator.or_, queries))
        if self.must_call_distinct(source.qs):
            # Filtering against a many-to-many field requires us to
            # call queryset.distinct() in order to avoid duplicate items
            # in the resulting queryset.
            # We try to avoid this if possible, for performance reasons.
            source.distinct(base)


class CellTitle:
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
        return self.key in self.controller.table.get_permanent

    def is_visible(self):
        return self.key in self.controller.visible_columns


class BoundCell:
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
                               strip_tags(self.as_html().replace('&nbsp;', ' ')))
        return default_value

    def to_python(self):
        if hasattr(self.bound_row.controller.table, 'to_python_%s' % self.key):
            cb = getattr(self.bound_row.controller.table, 'to_python_%s' % self.key)
            return cb(self.bound_row.controller.table, self.row_index, self.bound_row.row,
                      self.column.get_value(self.bound_row.row))
        return self.column.get_value(self.bound_row.row)

    def html_cell_attr(self):
        return self.column.html_cell_attr()

    def get_id(self):
        return self.key


class BoundRow:
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
