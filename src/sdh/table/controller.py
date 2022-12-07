import csv
import warnings
from datetime import datetime
from django.http import HttpResponseRedirect, HttpResponse
from django.template.loader import render_to_string
from django.http import JsonResponse

from .table import CellTitle, BoundRow
from .shortcuts import get_object_or_none, fn_value
from .paginator import Paginator
from .datasource import BaseDatasource


class TableController:
    def __init__(self, table, datasource, request, row_per_page=None, render_dict=None, paginator_class=None):
        self.table = table
        self.request = request
        self.profile = None
        self.filter_modified = False
        self.session_key = "tableview_%s" % self.table.id
        self.last_profile_key = "%s__last" % self.session_key
        self.source = datasource
        self.paginator_class = paginator_class or self.table.paginator_class or Paginator
        self.paginator = None
        self.visible_columns = self.table.get_default_visible
        self.sort_by = []
        self.sort_asc = True
        self.filter = {}
        self.form_filter_instance = None
        self.search_value = None
        self.allow_manage_profiles = True

        self.row_per_page = row_per_page
        self.table.request = self.request

        if row_per_page:
            self._init_paginator()

        if render_dict:
            warnings.warn("render_dict will be removed. Use template_context")
        self.render_dict = render_dict or {}

    def _init_paginator(self, page=1):
        self.paginator = self.paginator_class(self.source,
                                              page=page,
                                              row_per_page=self.row_per_page,
                                              request=self.request,
                                              skip_startup_recalc=True)

    def show_column(self, column_name):
        if column_name not in self.table.columns:
            return False

        if column_name in self.visible_columns:
            return False

        self.visible_columns.append(column_name)
        return True

    def get_paginated_rows(self):
        if self.paginator:
            row_iterator = self.paginator.get_items()
        else:
            row_iterator = self.source._clone()

        row_index = 0
        for row in row_iterator:
            row_index += 1
            yield BoundRow(self, row_index, row)

    def set_page(self, page_number):
        if self.paginator:
            self.paginator.page = page_number

    def set_sort(self, column_name):
        asc = True
        if column_name.startswith('-'):
            asc = False
            column_name = column_name[1:]

        if column_name in self.table.columns and column_name in self.table.sortable:
            self.sort_by = column_name
            self.sort_asc = asc

            column = self.table.columns[column_name]
            if hasattr(self.table, 'order_by_%s' % column_name):
                order_callback = getattr(self.table, 'order_by_%s' % column_name)
                order_callback(column, self.source, asc)
            else:
                if isinstance(self.source, BaseDatasource):
                    self.source.set_order(column.refname, asc)
                else:
                    if asc:
                        self.source = self.source.order_by(column.refname)
                    else:
                        self.source = self.source.order_by('-%s' % column.refname)
            return True
        return False

    def get_sort(self):
        if not self.sort_by:
            return ''
        if self.sort_asc:
            mode = ''
        else:
            mode = '-'

        return "%s%s" % (mode, self.sort_by)

    def apply_state(self, state):
        self.visible_columns = state.get('visible', self.table.get_default_visible)
        self.sort_by = state.get('sort_by')
        self.filter = state.get('filter', {}) or {}  # due some old profile save default as list
        if self.sort_by:
            self.set_sort(self.sort_by)

    def get_state(self):
        return {
            'visible': self.visible_columns,
            'sort_by': self.get_sort(),
            'filter': self.filter
        }

    def apply_search(self, value):
        self.search_value = value

    def restore(self, profile_id=None):
        from .models import TableViewProfile
        state = None

        if profile_id is None and self.last_profile_key in self.request.session:
            profile_id = self.request.session[self.last_profile_key]
        elif profile_id:
            self.request.session[self.last_profile_key] = profile_id

        profile_qs = TableViewProfile.objects.filter(tableview_name=self.table.id)
        if self.table.global_profile:
            profile_qs = profile_qs.filter(user__isnull=True)
        elif not fn_value(self.request.user.is_anonymous):
            profile_qs = profile_qs.filter(user=self.request.user)
            
        if profile_id == 'default' and self.request.user:
            self.profile, created = TableViewProfile.objects.get_or_create(
                tableview_name=self.table.id,
                user=self.request.user,
                is_default=True)
        elif profile_id is None and self.session_key not in self.request.session:
            # load default state
            self.profile = get_object_or_none(profile_qs,
                                              is_default=True)

        elif profile_id and profile_id.isdigit():
            self.profile = get_object_or_none(profile_qs,
                                              is_default=False,
                                              pk=profile_id)

        if self.session_key in self.request.session:
            state = self.request.session[self.session_key]

        if self.profile:
            state = self.profile.state

        if state:
            self.apply_state(state)

    def save(self):
        self.request.session["tableview_%s" % self.table.id] = self.get_state()

    def save_state(self, name=None):
        from .models import TableViewProfile

        state = self.get_state()
        dump = TableViewProfile.dump_state(state)

        kwargs = {
            'tableview_name': self.table.id,
            'defaults': {'dump': dump},
        }
        if self.table.global_profile:
            kwargs['user__isnull'] = True
        else:
            kwargs['user'] = self.request.user

        if name is None:
            kwargs['is_default'] = True
        else:
            kwargs['is_default'] = False
            kwargs['label'] = name

        profile, created = TableViewProfile.objects.get_or_create(**kwargs)

        if not created:
            profile.dump = dump
            profile.save()

        return {'status': 'OK',
                'id': profile.id,
                'created': created}

    def remove_profile(self, profile_id):
        from .models import TableViewProfile

        qs = TableViewProfile.objects.filter(id=profile_id,
                                             tableview_name=self.table.id,
                                             is_default=False
                                             )
        if self.table.global_profile:
            qs = qs.filter(user__isnull=True)
        else:
            qs = qs.filter(user=self.request.user)
        qs.delete()
        return {'status': 'OK'}

    @property
    def is_filter_active(self):
        return any(self.get_state()['filter'].values())

    def process_request(self, **kwargs):
        self.restore(self.request.GET.get('profile'))

        if self.request.is_ajax():
            if self.request.GET.get('action') == 'save_state':
                return self.save_state()

            if self.request.GET.get('action') == 'save_state_as':
                return self.save_state(self.request.GET.get('name'))

            if self.request.GET.get('action') == 'load_json':
                fun_name = 'ajax_%s' % self.request.GET.get('function', 'undef')
                if hasattr(self.table, fun_name):
                    fun = getattr(self.table, fun_name)
                    if callable(fun):
                        return fun(self.request)

            if self.request.GET.get('action') == 'remove_profile':
                return self.remove_profile(self.request.GET.get('value'))

            if self.request.GET.get('action') == 'load_page':
                self.process_form_filter()

                self.table.apply_filter(self.filter, self.source)

                if self.paginator:
                    self.paginator.calc()

                return JsonResponse(
                    {'page_count': self.paginator.get_page_count(),
                     'body': render_to_string(self.table.template_body_content,
                                              self.get_template_context(),
                                              self.request),
                     'paginator': render_to_string(self.table.template_paginator,
                                                   self.get_template_context(),
                                                   self.request)})

        if 'search' in self.request.GET:
            self.apply_search(self.request.GET['search'])
            self.table.apply_filter(self.filter, self.source)

        rc = self.process_form_filter()

        if 'sort_by' in self.request.GET:
            self.set_sort(self.request.GET.get('sort_by'))
            rc = HttpResponseRedirect('?profile=custom')

        if 'csv' in self.request.GET and self.table.csv_allow:
            return self.download_csv(self.request)

        if self.request.method == 'POST':
            if '_save_column_setup' in self.request.POST:
                prefix = "setup_%s_column_" % self.table.id
                self.visible_columns = []
                for key, value in self.request.POST.items():
                    if key.startswith(prefix):
                        self.show_column(value)
                rc = HttpResponseRedirect("?profile=custom")

        self.save()

        if rc:
            return rc

    def download_csv(self, request):
        self.paginator = None
        # Create the HttpResponse object with the appropriate CSV header.
        response = HttpResponse(content_type='text/csv', charset='utf-8')
        response['Content-Disposition'] = 'attachment; filename=%s_%s.csv' % (
            self.table.id,
            str(datetime.now()))

        writer = csv.writer(response)
        writer.writerow([cell.html_title() for key, cell in self.iter_title()])
        for row in self.get_paginated_rows():
            writer.writerow([cell.as_csv() for cell in row])
        return response

    def process_form_filter(self):
        if not self.table.filter_form:
            return

        if getattr(self.table.filter_form, 'has_queryset', False):
            params = {
                'queryset': self.source._clone()
            }
        else:
            params = {}

        if self.request.method == 'POST' and 'form_filter' in self.request.POST:
            form = self.table.filter_form(self.request.POST, request=self.request, **params)
            if form.is_valid():
                self.filter = form.cleaned_data
                self.save()
                return HttpResponseRedirect("?profile=custom")
        elif self.request.method == 'POST' and 'form_filter_reset' in self.request.POST:
            form = self.table.filter_form(None, initial={}, request=self.request, **params)
            self.filter = {}
        else:
            form = self.table.filter_form(request=self.request, initial=self.filter, **params)

        self.form_filter_instance = form

    def get_filter_detail(self):
        """
        Return detail of applied filter
        :return:
        """
        pass

    def get_saved_state(self):
        from .models import TableViewProfile

        if self.table.global_profile:
            return TableViewProfile.objects.filter(user__isnull=True,
                                                   tableview_name=self.table.id,
                                                   is_default=False).order_by('label')
        else:
            return TableViewProfile.objects.filter(user=self.request.user,
                                                   tableview_name=self.table.id,
                                                   is_default=False).order_by('label')

    def iter_columns(self):
        for key, column in self.table.columns.items():
            if key in self.table.get_permanent or key in self.visible_columns:
                yield key, column

    def iter_all_columns(self):
        for key, column in self.table.columns.items():
            yield key, column

    def iter_all_title(self):
        for key, column in self.iter_all_columns():
            yield key, CellTitle(self, key, column)

    def iter_title(self):
        for key, column in self.iter_columns():
            yield key, CellTitle(self, key, column)

    def get_template_context(self):
        kwargs = {
            'table': self.table,
            'filter_form': self.form_filter_instance,
            'controller': self,
            'context': self.table.get_template_context(self.request)
        }
        kwargs.update(**self.render_dict)
        return kwargs

    def as_html(self):
        if self.search_value:
            self.table.apply_search(self.search_value, self.source)
        else:
            self.table.apply_filter(self.filter, self.source)

        if self.paginator:
            self.paginator.calc()

        return render_to_string(self.table.template, self.get_template_context(), self.request)
