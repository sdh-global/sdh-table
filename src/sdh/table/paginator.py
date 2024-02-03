import math

from django.conf import settings
from django.http import Http404

from .shortcuts import atoi

"""
Typical template example
===========================

Template example for paginator::

    {% if paginator.is_paginate %}
    <div class='paginator'>
        {% if paginator.get_prev_page %}
            <a href='?page={{ paginator.get_prev_page }}'>&laquo;</a>
        {% endif %}
        {% if paginator.get_prev_page_group %}
            <a href='?page={{ paginator.get_prev_page_group }}'>...</a>
        {% endif %}

        {% for page in paginator.get_bar %}
           {% if page == paginator.page %}
              <span>{{ page }}</span>
           {% else %}
              <a href='?page={{ page }}'>{{ page }}</a>
           {% endif %}
        {% endfor %}

        {% if paginator.get_next_page_group %}
            <a href='?page={{ paginator.get_next_page_group }}'>...</a>
        {% endif %}
        {% if paginator.get_next_page %}
            <a href='?page={{ paginator.get_next_page }}'>&raquo;</a>
        {% endif %}
    </div>
    {% endif %}


"""


class Paginator(object):
    """ Paginator tool

        For use ``Paginator`` need to pass into template context
        instance of ``Paginator`` object with full query_set and
        current page number.

        Optional argument ``row_per_page`` can be omitted, then object
        will look for ``ROW_PER_PAGE`` in project settings file.
    """

    def __init__(self, queryset, page=None, row_per_page=None, request=None,
                 skip_startup_recalc=False, segment=None):
        self._queryset = queryset
        self.request = request
        self._pages = None
        self.segment = segment or 5
        self._page = None
        self.row_per_page = row_per_page or settings.PAGINATOR_PER_PAGE
        self._hits = 0

        if page is not None or request is not None and self.row_per_page != 'all':
            if not skip_startup_recalc:
                self.calc(page)

    def calc(self, page=None):
        if self.request and 'page' in self.request.GET and page is None:
            page = self.request.GET['page']
        self._page = atoi(page, 1)

        if isinstance(self._queryset, list):
            self._hits = len(self._queryset)
        else:
            self._hits = int(self._queryset.count())

        self._pages = int(math.ceil(float(self._hits) / float(self.row_per_page)))
        if not self._pages:
            self._pages = 1

        if self._page < 1 or self._page > self._pages:
            raise Http404

    @property
    def page(self):
        if self._page is None:
            self.calc()
        return self._page

    @page.setter
    def page(self, value):
        self.calc(value)

    def get_start_url(self):
        url = '?'
        if self.request and self.request.GET:
            qset = self.request.GET.copy()
            if 'page' in qset:
                del qset['page']

            if len(qset) > 0:
                url += qset.urlencode()
                url += '&'

        return url

    def get_page_count(self):
        return self._pages

    def get_rows_count(self):
        return self._hits

    def get_offset(self):
        start = (self.page - 1) * atoi(self.row_per_page, 1)
        end = self.page * atoi(self.row_per_page)
        return start, end

    def get_items(self):
        """ Return query set for current page """
        if self.row_per_page == 'all':
            return self._queryset

        start, end = self.get_offset()
        return self._queryset[start:end]

    def get_bar(self):
        """ Return list of page numbers for current segment """
        bar = []
        for page in range(self.page - self.segment, self.page + self.segment + 1):
            if page <= 0 or page > self.get_page_count():
                continue

            bar.append(page)
        return bar

    def get_prev_page(self):
        if self.page - 1 <= 0:
            return None

        return self.page - 1

    def get_next_page(self):
        if self.page + 1 > self.get_page_count():
            return None

        return self.page + 1

    def get_prev_page_group(self):
        if self.page - self.segment * 2 - 1 <= 0:
            return None
        return self.page - self.segment * 2 - 1

    def get_prev_page_segment(self):
        if self.page - self.segment - 1 <= 0:
            return None
        return self.page - self.segment - 1

    def get_next_page_group(self):
        if self.page + self.segment * 2 + 1 > self.get_page_count():
            return None
        return self.page + self.segment * 2 + 1

    def get_next_page_segment(self):
        if self.page + self.segment + 1 > self.get_page_count():
            return None
        return self.page + self.segment + 1

    def get_last_page(self):
        return int(self.get_page_count())

    def is_paginate(self):
        return self.row_per_page != 'all' and self.get_page_count() > 1

    def set_page_by_position(self, position):
        self.page = int((position - 1) / self.row_per_page) + 1

    def set_inverted_page_by_position(self, position):
        """ set inverted paginator page

         Example: inverted paginator for 33 items:

         page4: 33..24
         page3: 23..14
         page2: 13..4
         page1: 3..1

        """
        page = None
        i = self.get_rows_count() + 1
        for p in range(1, self.get_page_count() + 1):  # [1,2,3,4]
            i -= self.row_per_page
            if i <= position:
                page = p
                break
        self.page = page


class LazyPaginator(Paginator):

    def __init__(self, queryset, page=None, row_per_page=None, request=None,
                 skip_startup_recalc=False, segment=None):
        super(LazyPaginator, self).__init__(queryset, page, row_per_page, request,
                                            skip_startup_recalc, segment)
        self._last_page = None
        self._rows = []
        self.segment = segment or 3

    def get_next_page_group(self):
        if self.last_page and self.page + self.segment * 2 + 1 > self.last_page:
            return None
        return self.page + self.segment * 2 + 1

    @property
    def last_page(self):
        return self._last_page

    @last_page.setter
    def last_page(self, value):
        self._last_page = value
        self._pages = value

    def get_items(self):
        if len(self._rows) > self.row_per_page:
            return self._rows[0:self.row_per_page]
        return self._rows

    def _fetch_rows(self):
        start, end = self.get_offset()
        self._rows = list(self._queryset[start:end + 1])

    def _find_rows(self):
        page = max(1, self._page - self.segment)
        row_per_page = atoi(self.row_per_page, 1)
        row_per_segment = row_per_page * self.segment
        start = (page - 1) * row_per_page
        end = start + row_per_segment
        self._rows = list(self._queryset[start:end])
        rows_count = len(self._rows)
        if rows_count:
            page_count = rows_count // row_per_page
            if not rows_count % row_per_page:
                page_count -= 1
            self._page = self.last_page = page + page_count
            self._rows = self._rows[page_count * self.row_per_page:]
        else:
            self._page = 1
            self._fetch_rows()

    def calc(self, page=None):
        if self.request and 'page' in self.request.GET and page is None:
            page = self.request.GET['page']
        _page = atoi(page, 1)
        if self.last_page and _page > self.last_page:
            self._page = self.last_page
        else:
            self._page = _page

        self._fetch_rows()

        if not self._pages:
            rows_count = len(self._rows)
            if not rows_count:
                if self._page == 1:
                    self.last_page = 1
                    return
                if self.last_page:
                    self._page = self.last_page
                    self._fetch_rows()
                else:
                    self._find_rows()

            rows_count = len(self._rows)
            if rows_count > self.row_per_page:
                self.set_page_count(self._page + 1)
            else:
                self.last_page = self._page

        if self._page < 1:
            raise Http404

    def get_bar(self):
        """ Return list of page numbers for current segment """
        bar = []
        for page in range(self.page - self.segment, self.page + self.segment + 1):
            if page <= 0 or self.last_page and page > self.last_page:
                continue
            bar.append(page)
        return bar

    def set_page_count(self, value):
        self._pages = value

    def is_paginate(self):
        return True


class LazySegmentPaginator(Paginator):

    def calc(self, page=None):
        if self.request and 'page' in self.request.GET and page is None:
            page = self.request.GET['page']
        self._page = atoi(page, 1)

        _hits = self._queryset[(self._page - 1) * self.row_per_page:
                               self._page * self.row_per_page + self.segment * self.row_per_page].count()
        if _hits:
            self._pages = self._page + _hits // self.row_per_page

        if not self._pages:
            self._pages = 1

        if self._page < 1 or self._page > self._pages:
            raise Http404

    def set_inverted_page_by_position(self, position):
        pass
