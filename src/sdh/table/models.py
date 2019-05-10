from __future__ import unicode_literals

import pickle
import codecs

from django.db import models
from django.conf import settings


class TableViewProfile(models.Model):
    PICKLE_PROTOCOL = 2  # for backwards compatibility with Python2.x

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.CASCADE, related_name='+')

    tableview_name = models.CharField(max_length=255)
    label = models.CharField(max_length=255, null=True, blank=True)
    is_default = models.BooleanField(default=False)
    dump = models.TextField(default='')

    class Meta:
        db_table = 'tableview_profile'

    @property
    def state(self):
        dump = codecs.decode(self.dump, 'hex_codec')
        try:
            return pickle.loads(dump)
        except (pickle.UnpicklingError, EOFError, AttributeError, ImportError, IndexError):
            pass

    @classmethod
    def dump_state(cls, data):
        dump = pickle.dumps(data, cls.PICKLE_PROTOCOL)
        return codecs.encode(dump, 'hex_codec')
