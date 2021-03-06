# Generated by Django 2.2.6 on 2019-10-03 21:54

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('transfers', '0007_auto_20191003_2102'),
    ]

    operations = [
        migrations.AlterField(
            model_name='transferitem',
            name='exrate_market',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='items', to='transfers.ExchangeRate'),
        ),
        migrations.AlterField(
            model_name='transferitem',
            name='exrate_service',
            field=models.DecimalField(decimal_places=4, max_digits=20),
        ),
    ]
