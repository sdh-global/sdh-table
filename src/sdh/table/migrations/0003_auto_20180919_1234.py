from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('table', '0002_auto_20180310_1118'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tableviewprofile',
            name='user',
            field=models.ForeignKey(blank=True, null=True,
                                    on_delete=django.db.models.deletion.CASCADE,
                                    related_name='+',
                                    to=settings.AUTH_USER_MODEL),
        ),
    ]
