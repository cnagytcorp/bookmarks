# Generated by Django 2.2.7 on 2019-12-03 13:59

from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('links', '0015_auto_20191203_1138'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='page',
            unique_together={('name', 'user')},
        ),
    ]
