# Generated by Django 2.2.6 on 2019-10-17 09:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('transfers', '0014_delete_repo'),
    ]

    operations = [
        migrations.CreateModel(
            name='TransferAmount',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('value', models.PositiveSmallIntegerField(unique=True)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'db_table': 'transfer_amounts',
            },
        ),
    ]
