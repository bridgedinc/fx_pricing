# Generated by Django 2.2.6 on 2019-10-05 12:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('transfers', '0009_auto_20191003_2249'),
    ]

    operations = [
        migrations.AlterField(
            model_name='transferitem',
            name='exrate_market',
            field=models.DecimalField(decimal_places=4, max_digits=20, null=True),
        ),
    ]
