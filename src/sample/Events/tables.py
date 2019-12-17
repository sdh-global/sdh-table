from sdh.table import table, widgets


class EventList(table.TableView):
    name = widgets.LabelWidget('Name', refname='name')

    class Meta:
        permanent = ('name', )
        sortable = ('name', )
        search = ('name',)
