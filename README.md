# sdh.table

A server-rendered table/grid engine for Django. You declare a `TableView` as a set
of columns (widgets) plus a small `Meta`, wire it to a queryset through a
`TableController`, and get sorting, filtering, searching, pagination, CSV export,
and per-user "saved view" profiles — all driven by GET/POST params and rendered
through ordinary Django templates.

Requires Django >= 5.2 and Python >= 3.11.

## Installation

```bash
pip install sdh.table
```

Add the app so its templates, templatetags and the `TableViewProfile` model are
available, then run `makemigrations`/`migrate` as usual for your project:

```python
INSTALLED_APPS = [
    ...,
    "sdh.table",
]

PAGINATOR_PER_PAGE = 25  # default page size, can be overridden per-controller
```

## Quick start

Declare a table next to your models (conventionally in a `tables.py` per app):

```python
# blog/tables.py
from sdh.table import table, widgets


class ArticleList(table.TableView):
    title = widgets.HrefWidget('Title', refname='title', reverse='article-detail', reverse_column='id')
    author = widgets.LabelWidget('Author', refname='author__name')
    published_at = widgets.LocalDateWidget('Published')

    class Meta:
        permanent = ('title',)
        default_visible = ('title', 'author', 'published_at')
        sortable = ('title', 'author', 'published_at')
        search = ('title', 'author__name')
```

Wire it up in a view:

```python
# blog/views.py
from django.shortcuts import render
from sdh.table import controller, datasource

from .tables import ArticleList
from .models import Article


def article_list(request):
    qs = Article.objects.select_related('author')
    source = datasource.QSDataSource(qs)

    cnt = controller.TableController(ArticleList('article_list'), source, request, row_per_page=25)

    rc = cnt.process_request()
    if rc:
        # process_request returns an HttpResponse for AJAX actions
        # (sort links, save/remove profile, CSV export, ...) — pass it straight through
        return rc

    return render(request, "blog/article_list.html", {'table': cnt})
```

And render it — the context variable is conventionally named `table` even though
it holds the *controller* instance:

```html
{# blog/article_list.html #}
{% extends "base.html" %}
{% block content %}
  {{ table.as_html }}
{% endblock %}
```

`table.as_html` renders `Meta.template` (`sdh/table/table_body.html` by default),
which in turn includes `sdh/table/table_head.html` for column headers/sort links
and iterates `controller.get_paginated_rows` for the body. Override those
templates (via `Meta.template` / `Meta.template_body_content` /
`Meta.template_paginator`) to fit your own markup/CSS framework.

## Core concepts

### `TableView` and `Meta`

Columns are declared as class attributes using widget instances; `Meta` controls
everything else:

```python
class ArticleList(table.TableView):
    class Meta:
        permanent = ('title',)              # always visible, can't be hidden by the user
        default_visible = ('title', 'author')  # visible by default when a user has no saved state
        sortable = ('title', 'author', 'published_at')
        default_sorting = '-published_at'    # applied when the user hasn't picked a sort
        filter_form = ArticleFilterForm       # see "Filtering" below
        search = ('title', 'author__name')    # see "Searching" below
        template = 'blog/article_table.html'  # override the outer table template
        template_context = {'title': 'Articles'}
        csv_allow = True
        paginator_class = None                # defaults to sdh.table.Paginator
        global_profile = False                # see "Saved profiles" below
        title = 'Articles'
```

`permanent` and `default_visible` also accept the sentinel `table.ALL_FIELDS`
(`'__all__'`) to mean "every declared column".

### Widgets

A widget both formats a cell's HTML and knows how to pull its value off a row via
`refname` (a Django `__`-lookup style path, resolved with `getattr`/callables —
works on model instances, dicts-as-objects, or annotated queryset rows alike):

- `LabelWidget` — plain value, no special formatting.
- `DateTimeWidget` / `LocalDateTimeWidget` / `LocalDateWidget` — localized
  date/time formatting; the `Local*` variants convert aware datetimes to naive
  local time before formatting.
- `HrefWidget` — renders the value as a link; either a static `href=` or a
  `reverse=` URL name plus `reverse_column` (a field or tuple of fields whose
  values become the `reverse()` args).
- `ConditionHrefWidget` — like `HrefWidget`, but only links when a `condition`
  callable (`condition(row, request)`) and/or an `acl` attribute check passes;
  otherwise renders the plain value.
- `TemplateWidget` — renders a small template with `{item, value, row, index, request}`
  in context, for anything more custom than a single formatted value.
- `BooleanWidget` — a `TemplateWidget` preconfigured to render a yes/no/null icon
  template; override `template=` to reskin it.

Writing your own widget is the normal way to add domain-specific formatting
(currency, badges, computed properties, etc.). Subclass `BaseWidget`, pop any
extra constructor kwargs before calling `super().__init__`, and override
`html_cell(self, row_index, row, **kwargs)`:

```python
from sdh.table import widgets
from django.utils.safestring import mark_safe

class CurrencyWidget(widgets.BaseWidget):
    def __init__(self, *args, decimal_pos=2, **kwargs):
        super().__init__(*args, **kwargs)
        self.decimal_pos = decimal_pos
        self.cell_attr = self.cell_attr or {'style': 'text-align: right'}

    def html_cell(self, row_index, row, **kwargs):
        value = self.get_value(row)
        if value is None:
            return ' '
        return mark_safe('$%.*f' % (self.decimal_pos, value))
```

### Datasources

`TableController` doesn't care whether it's iterating a Django queryset or
something else, as long as it gets an object implementing the small
`BaseDatasource` protocol (`set_order`, `set_limit`, `count`, `__iter__`,
slicing). `QSDataSource` is the queryset-backed implementation you'll use almost
everywhere:

```python
source = datasource.QSDataSource(Article.objects.all(), primary_key='pk')
```

It adds `.filter(...)`, `.exclude(...)`, `.extra(...)` and `.distinct(base)`
passthroughs to the wrapped queryset, and a stable `set_order(field, asc)` that
always appends the primary key as a tiebreaker.

For non-ORM sources (raw SQL, an external API, an in-memory list), subclass
`BaseDatasource` directly and implement whatever subset of the protocol your
paginator and filters actually touch — `SqlDataSource` is a minimal starting
point for wrapping raw SQL.

### `TableController`

`TableController(table, datasource, request, row_per_page=None, render_dict=None,
paginator_class=None)` binds everything together for one request:

- `process_request()` reads GET/POST, restores a saved profile, applies sorting,
  filtering and search, and handles the controller's built-in AJAX actions
  (`action=save_state`, `save_state_as`, `remove_profile`, `load_page`, and
  `load_json&function=X` which dispatches to `table.ajax_X(request)`). If it
  returns a truthy value, that's an `HttpResponse` you must return from your view
  as-is.
- `as_html()` applies search/filter, runs the paginator, and renders `Meta.template`.
- `get_paginated_rows()` yields `BoundRow` objects (iterate them for `BoundCell`
  per visible column) — this is also the hook to override for prefetching (see
  "Extending" below).
- `render_dict` is merged into the template context, for extra template-only
  variables that don't belong on the model or the table.

### Filtering

Give the table a plain Django form via `Meta.filter_form` and override
`apply_filter(self, cleaned_data, source)` on the `TableView` to translate the
form's cleaned data into a query. Mutate `source` in place — don't reassign it:

```python
class ArticleFilterForm(forms.Form):
    author = forms.ModelChoiceField(Author.objects.all(), required=False)
    published_after = forms.DateField(required=False)


class ArticleList(table.TableView):
    class Meta:
        filter_form = ArticleFilterForm

    def apply_filter(self, cleaned_data, source):
        if cleaned_data.get('author'):
            source.filter(author=cleaned_data['author'])
        if cleaned_data.get('published_after'):
            source.filter(published_at__gte=cleaned_data['published_after'])
```

If the form needs the current queryset (e.g. to scope a `ModelChoiceField`'s
options), set `filter_form.has_queryset = True`; the controller will then
instantiate it with `queryset=source._clone()`.

### Searching

`Meta.search` lists the fields a free-text `?search=` box matches against with
`icontains` by default. Prefix a field with `^`, `=`, `@` or `$` to switch to
`istartswith`, `iexact`, a backend's native full-text `search` lookup, or
`iregex` respectively (mirrors Django admin's `search_fields` prefixes). For
anything beyond simple per-field lookups (full-text vectors, combining fields
with `OR`, cleaning the raw input), override `apply_search(self, search_value,
source)` on the `TableView`.

### Sorting

List sortable columns in `Meta.sortable`; the header template turns them into
`?sort_by=column` / `?sort_by=-column` links. Provide `Meta.default_sorting` for
the sort to use before the user picks one. For anything beyond
`source.order_by(refname)` — computed/annotated columns, a stable secondary key,
delegating to `source.set_order(...)` — override `order_by_<column_name>(self,
column, source, asc)`:

```python
def order_by_published_at(self, column, source, asc):
    source.set_order('published_at', asc)  # QSDataSource appends the PK for you
```

### Pagination

`Paginator` computes page count from `datasource.count()` and slices the
datasource for the current page; `LazyPaginator` avoids ever calling `count()`
by fetching one segment ahead/behind and inferring page boundaries from what
comes back (useful for very large or expensive-to-count sources), and
`LazySegmentPaginator` is a lighter-weight middle ground that estimates the page
count from one bounded lookahead query. Pass `row_per_page='all'` to disable
paging entirely while still getting a `Paginator` object in the template
context.

Set `paginator_class` in `Meta` (or pass `paginator_class=` to the controller) to
swap in your own subclass — the usual reasons are supporting `row_per_page='all'`
dynamically, streaming rows in fixed-size chunks for a background export, or
changing how many page-number links `get_bar()` returns:

```python
class ChunkedExportPaginator(paginator.Paginator):
    def get_items(self):
        # stream everything in fixed-size chunks instead of one page
        ...
```

### Per-column render hooks

Beyond what a widget renders by default, a `TableView` subclass can define
per-column hooks the controller looks up dynamically by column name — all
receive `(self, table, row_index, row, value)` where `value` is whatever the
widget's `get_value(row)` returned:

- `render_<column>` — override the cell's HTML entirely.
- `render_csv_<column>` — override what goes into a CSV export row for this
  column (falls back to the stripped/plain-text version of the rendered HTML).
- `to_python_<column>` — return a plain Python value for this cell, e.g. for
  code that consumes `BoundCell.to_python()` directly instead of exporting CSV.
- `cell_class_<column>` / `cell_style_<column>` — return a CSS class / inline
  style string for the `<td>`.

```python
class ArticleList(table.TableView):
    def render_published_at(self, table, row_index, row, value):
        return value.strftime('%b %Y') if value else '—'

    def cell_class_published_at(self, table, row_index, row, value):
        return 'text-muted' if value is None else ''
```

`get_row_class(self, controller, row)` on the `TableView` similarly lets you set
a CSS class on the whole `<tr>`.

### CSV export

Set `Meta.csv_allow = True` and add `&csv` to the URL (or link to it) — the
controller streams `iter_title()`/`get_paginated_rows()` straight to a CSV
`HttpResponse` using `Meta.csv_dialect` (defaults to `csv.excel`). This is meant
for modest, synchronous exports; for large exports, drive the same building
blocks (`iter_title()`, `get_paginated_rows()`, `BoundCell.as_html()`/`.to_python()`)
from your own background task instead of calling `download_csv` directly.

### AJAX endpoints

`Meta`-less, but built into the controller's dispatch: a request with
`X-Requested-With: XMLHttpRequest` and `?action=load_json&function=foo` calls
`table.ajax_foo(request)` if it exists and is callable — a lightweight way to
expose custom AJAX behavior scoped to a single table without a separate view.

### Saved profiles

`TableViewProfile` persists a user's column visibility, sort and filter state
(pickled, keyed by table id) so it survives across sessions. The controller
exposes this through its built-in AJAX actions:

- `?action=save_state` — save the current state as the user's default for this table.
- `?action=save_state_as&name=...` — save it as a new named profile.
- `?action=remove_profile&value=<id>` — delete a saved (non-default) profile.
- `?profile=<id|default|custom>` on any request — load that profile's state
  before applying the rest of the request.

Set `Meta.global_profile = True` for tables where saved views should be shared
across all users instead of scoped per-user (e.g. a shared report configuration).
`controller.get_saved_state()` returns the current user's (or global) saved
profiles for building a "load saved view" menu — see the `{% tableview_profiles %}`
template tag below for the same query as a template-only shortcut.

### Templates and template tags

`{% load tableview %}` provides:

- `{% tableview_profiles user table_id as var %}` — assigns the queryset of
  saved (non-default) profiles for `table_id`/`user` into `var`, for building a
  saved-views menu without going through the controller.
- `{% args querydict key value %}` — returns `querydict` with `key` set to
  `value`, URL-encoded; used for building sort/pagination/filter links that
  preserve the rest of the current query string:

  ```html
  <a href="?{% args request.GET 'sort_by' 'published_at' %}">Published</a>
  ```

## Extending `TableController`

Subclassing `TableController` is the standard extension point for
project-wide behavior — anything from wiring in your JS/AJAX conventions to
prefetching related data for a page of rows:

```python
from sdh.table import controller
from sdh.table.table import BoundRow


class PrefetchingController(controller.TableController):
    def get_paginated_rows(self):
        rows = list(self.paginator.get_items()) if self.paginator else list(self.source._clone())
        # warm a shared cache for whatever the widgets/render hooks will look up per-row
        Author.objects.prefetch_related_for(rows)
        for index, row in enumerate(rows, start=1):
            yield BoundRow(self, index, row)
```

`get_template_context()` and `as_html()` are the other common override points —
e.g. adding a flag to the template context, or swapping in a partial template
when responding to an AJAX/HTMX-style request.

## Permission checks

There's no built-in ACL layer — `ConditionHrefWidget`'s `condition=`/`acl=`
hooks exist for simple per-cell cases, but most projects check permissions the
same way they would in any other view: gate the whole view up front, and for
row- or cell-level checks, read `request` off the widget's `**kwargs` (widgets
receive `request=controller.request` when rendering) or `self.request` on the
`TableView` (set by the controller before rendering) inside a `render_<column>`
or `cell_class_<column>` hook.

## Management command

`sdh_update_table_columns` renames a column key inside every saved
`TableViewProfile` for a given table — run it after renaming a column in code so
existing users' saved visibility/sort state doesn't silently drop the renamed
column:

```bash
./manage.py sdh_update_table_columns --name article_list --column old_name:new_name
```
