# Generated by Django 2.2.7 on 2019-12-03 11:38

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('links', '0014_auto_20191203_1039'),
    ]

    operations = [
        migrations.RenameField(
            model_name='page',
            old_name='column_order_2',
            new_name='collection_order_2',
        ),
        migrations.RenameField(
            model_name='page',
            old_name='column_order_3',
            new_name='collection_order_3',
        ),
        migrations.RenameField(
            model_name='page',
            old_name='column_order_4',
            new_name='collection_order_4',
        ),
        migrations.RenameField(
            model_name='page',
            old_name='column_order_5',
            new_name='collection_order_5',
        ),
    ]