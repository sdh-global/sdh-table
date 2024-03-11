from django.db import models
from django.conf import settings


class Event(models.Model):
    name = models.CharField(max_length=20)
    start_date = models.DateField()

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT)

    is_public = models.BooleanField()

    created_stamp = models.DateTimeField()
    changed_stamp = models.DateTimeField()

    class Meta:
        db_table = 'event'
