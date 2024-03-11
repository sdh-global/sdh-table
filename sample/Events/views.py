from django.shortcuts import get_object_or_404, redirect, render, HttpResponse, Http404

from sdh.table import controller, datasource

from .tables import EventList
from .models import Event


def events_list(request):

    qs = Event.objects.all()

    source = datasource.QSDataSource(qs)

    table = EventList('event_list')

    cnt = controller.TableController(table, source, request)

    rc = cnt.process_request()
    if rc:
        return rc

    return render(request, "Events/list.html",
                  {'table': cnt})
