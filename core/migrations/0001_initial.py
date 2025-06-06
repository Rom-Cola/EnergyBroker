# Generated by Django 5.2.1 on 2025-05-25 13:15

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='EnergyData',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField()),
                ('price', models.FloatField()),
                ('demand', models.FloatField()),
                ('supply', models.FloatField()),
                ('temperature', models.FloatField(blank=True, null=True)),
                ('wind_generation', models.FloatField(blank=True, null=True)),
                ('solar_generation', models.FloatField(blank=True, null=True)),
            ],
            options={
                'ordering': ['timestamp'],
            },
        ),
    ]
