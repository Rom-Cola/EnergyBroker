from django.shortcuts import render
from django.http import HttpResponse
from .models import EnergyData
import pandas as pd
import json


def index(request):
    return HttpResponse("Hello, world! This is the EnergyBroker core app.")


def energy_list(request):
    energy_data = EnergyData.objects.all().order_by('-timestamp')[:100]
    return render(request, 'core/energy_list.html', {'energy_data': energy_data})


def energy_dashboard(request):
    # Отримання даних з бази даних
    # Тут ми візьмемо всі дані, але для великих обсягів краще обмежувати.
    energy_data_qs = EnergyData.objects.all().order_by('timestamp')

    # Перетворюємо QuerySet в Pandas DataFrame
    df = pd.DataFrame(list(energy_data_qs.values()))

    labels = []
    prices = []
    demand = []
    supply = []

    if not df.empty:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        # Форматуємо дату для JavaScript/Chart.js
        labels = df['timestamp'].dt.strftime('%Y-%m-%d %H:%M').tolist()
        prices = df['price'].tolist()
        demand = df['demand'].tolist()
        supply = df['supply'].tolist()

    context = {
        'labels': json.dumps(labels),
        'prices': json.dumps(prices),
        'demand': json.dumps(demand),
        'supply': json.dumps(supply),
    }
    return render(request, 'core/energy_dashboard.html', context)