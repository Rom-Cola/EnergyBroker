from django.shortcuts import render
from django.http import HttpResponse
from .models import EnergyData, PricePrediction
import pandas as pd
import json
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from datetime import datetime, timedelta, timezone
from django.utils import timezone as django_timezone


def index(request):
    return HttpResponse("Hello, world! This is the EnergyBroker core app.")


def energy_list(request):
    energy_data_list = EnergyData.objects.all()

    # --- Фільтрація ---
    filters = {
        'start_date': request.GET.get('start_date'),
        'end_date': request.GET.get('end_date'),
        'min_price': request.GET.get('min_price'),
        'max_price': request.GET.get('max_price'),
        'min_temp': request.GET.get('min_temp'),
        'max_temp': request.GET.get('max_temp'),
        'sort_by': request.GET.get('sort_by', '-timestamp'),
    }

    if filters['start_date']:
        try:
            start_datetime = datetime.strptime(filters['start_date'], '%Y-%m-%d')
            energy_data_list = energy_data_list.filter(timestamp__gte=start_datetime)
        except ValueError:
            pass

    if filters['end_date']:
        try:
            end_datetime = datetime.strptime(filters['end_date'], '%Y-%m-%d')
            end_datetime = end_datetime.replace(hour=23, minute=59, second=59)
            energy_data_list = energy_data_list.filter(timestamp__lte=end_datetime)
        except ValueError:
            pass

    if filters['min_price']:
        try:
            min_price = float(filters['min_price'])
            energy_data_list = energy_data_list.filter(price__gte=min_price)
        except ValueError:
            pass
    if filters['max_price']:
        try:
            max_price = float(filters['max_price'])
            energy_data_list = energy_data_list.filter(price__lte=max_price)
        except ValueError:
            pass

    if filters['min_temp']:
        try:
            min_temp = float(filters['min_temp'])
            energy_data_list = energy_data_list.filter(temperature__gte=min_temp)
        except ValueError:
            pass
    if filters['max_temp']:
        try:
            max_temp = float(filters['max_temp'])
            energy_data_list = energy_data_list.filter(temperature__lte=max_temp)
        except ValueError:
            pass

    # --- Сортування ---
    valid_sort_fields = [
        'timestamp', '-timestamp', 'price', '-price', 'demand', '-demand',
        'temperature', '-temperature', 'wind_generation', '-wind_generation',
        'solar_generation', '-solar_generation', 'radiation_direct_horizontal',
        '-radiation_direct_horizontal', 'radiation_diffuse_horizontal', '-radiation_diffuse_horizontal'
    ]
    if filters['sort_by'] in valid_sort_fields:
        energy_data_list = energy_data_list.order_by(filters['sort_by'])
    else:
        energy_data_list = energy_data_list.order_by('-timestamp')

    # --- Пагінація ---
    paginator = Paginator(energy_data_list, 50)  # 50 записів на сторінку

    page_number = request.GET.get('page')
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    page_range_elided = paginator.get_elided_page_range(
        number=page_obj.number,
        on_each_side=2,
        on_ends=1
    )

    get_copy = request.GET.copy()
    if 'page' in get_copy:
        del get_copy['page']
    query_string = get_copy.urlencode()

    context = {
        'page_obj': page_obj,
        'filters': filters,
        'query_string': query_string,
        'page_range_elided': page_range_elided,
    }
    return render(request, 'core/energy_list.html', context)


def energy_dashboard(request):
    # --- Фільтрація для дашборду ---
    user_start_date_str = request.GET.get('start_date')
    user_end_date_str = request.GET.get('end_date')

    # Отримуємо останню доступну дату з фактичних даних (якщо є)
    last_actual_data_timestamp = EnergyData.objects.order_by('-timestamp').values_list('timestamp', flat=True).first()
    if last_actual_data_timestamp:
        # Для дефолту показуємо останні 30 днів фактичних даних + 7 днів прогнозів
        default_end_date = last_actual_data_timestamp.date() + timedelta(days=7)  # Включаємо прогнози
        default_start_date = last_actual_data_timestamp.date() - timedelta(
            days=30)  # 30 днів назад від останніх фактичних
    else:
        # Fallback, якщо немає даних
        default_end_date = datetime(2019, 12, 31).date()
        default_start_date = default_end_date - timedelta(days=30)

    start_date_obj = default_start_date
    end_date_obj = default_end_date

    # Обробка вхідних даних від користувача
    if user_start_date_str:
        try:
            start_date_obj = datetime.strptime(user_start_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    if user_end_date_str:
        try:
            end_date_obj = datetime.strptime(user_end_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    # Передаємо фактичні дати, за якими відбувається фільтрація, в шаблон
    dashboard_filters = {
        'start_date': start_date_obj.isoformat(),
        'end_date': end_date_obj.isoformat(),
    }

    # Отримуємо дані з бази даних за вказаним/дефолтним діапазоном
    start_datetime_filter = datetime.combine(start_date_obj, datetime.min.time(), tzinfo=timezone.utc)
    end_datetime_filter = datetime.combine(end_date_obj, datetime.max.time(), tzinfo=timezone.utc)

    # Завантажуємо фактичні дані
    energy_data_qs = EnergyData.objects.filter(
        timestamp__gte=start_datetime_filter,
        timestamp__lte=end_datetime_filter
    ).order_by('timestamp')

    df_actual = pd.DataFrame(list(energy_data_qs.values(
        'timestamp', 'price', 'demand', 'supply', 'temperature',
        'wind_generation', 'solar_generation',
        'radiation_direct_horizontal', 'radiation_diffuse_horizontal'
    )))

    # Завантажуємо прогнозовані дані
    prediction_data_qs = PricePrediction.objects.filter(
        timestamp__gte=start_datetime_filter,
        timestamp__lte=end_datetime_filter
    ).order_by('timestamp')

    df_predictions = pd.DataFrame(list(prediction_data_qs.values()))

    # Об'єднуємо фактичні та прогнозовані дані для відображення на графіку цін
    # Перевіряємо, чи df_predictions не порожній, перш ніж вибирати стовпці
    df_combined_prices = pd.DataFrame()  # Створюємо порожній DataFrame за замовчуванням
    if not df_predictions.empty:
        # Переконаємось, що 'predicted_price' та 'timestamp' існують
        if 'predicted_price' in df_predictions.columns and 'timestamp' in df_predictions.columns:
            df_combined_prices = pd.merge(
                df_actual[['timestamp', 'price']],
                df_predictions[['timestamp', 'predicted_price']],
                on='timestamp',
                how='left'
            )
        else:
            # Якщо прогнозовані дані є, але не мають потрібних стовпців (хоча не повинні)
            df_combined_prices = df_actual[['timestamp', 'price']].copy()
            df_combined_prices['predicted_price'] = None  # Додаємо порожній стовпець

    else:
        # Якщо df_predictions порожній, тоді df_combined_prices містить лише фактичні ціни
        df_combined_prices = df_actual[['timestamp', 'price']].copy()
        df_combined_prices['predicted_price'] = None  # Додаємо порожній стовпець, щоб уникнути KeyError

    labels = []
    prices_actual = []
    prices_predicted = []
    demand = []
    supply = []
    wind_gen = []
    solar_gen = []
    temperature = []
    rad_direct = []
    rad_diffuse = []
    recommendations = []

    if not df_actual.empty:
        df_actual['timestamp'] = pd.to_datetime(df_actual['timestamp'])
        labels = df_actual['timestamp'].dt.strftime('%Y-%m-%d %H:%M').tolist()

        # Використовуємо df_actual для цих даних
        demand = df_actual['demand'].fillna(0).tolist()
        if 'supply' in df_actual.columns:
            # Щоб уникнути FutureWarning, явно перетворюємо в float, якщо стовпець існує
            supply = df_actual['supply'].astype(float).fillna(0).tolist()
        else:
            supply = [0] * len(df_actual)

        wind_gen = df_actual['wind_generation'].fillna(0).tolist()
        solar_gen = df_actual['solar_generation'].fillna(0).tolist()
        temperature = df_actual['temperature'].fillna(0).tolist()
        rad_direct = df_actual['radiation_direct_horizontal'].fillna(0).tolist()
        rad_diffuse = df_actual['radiation_diffuse_horizontal'].fillna(0).tolist()

        df_combined_prices['timestamp'] = pd.to_datetime(df_combined_prices['timestamp'])
        price_map = df_combined_prices.set_index('timestamp').to_dict('index')

        for ts_label in labels:
            # Парсимо ts_label, додаючи UTC timezone, якщо його немає
            try:
                ts_obj = datetime.strptime(ts_label, '%Y-%m-%dT%H:%M:%S%z')
            except ValueError:
                ts_obj = datetime.strptime(ts_label, '%Y-%m-%d %H:%M').replace(tzinfo=timezone.utc)

            actual_p = price_map.get(ts_obj, {}).get('price')
            prices_actual.append(actual_p if pd.notna(actual_p) else None)

            predicted_p = price_map.get(ts_obj, {}).get('predicted_price')
            prices_predicted.append(predicted_p if pd.notna(predicted_p) else None)

    # Отримуємо рекомендації з прогнозованих даних за період дашборду
    if not df_predictions.empty:
        df_predictions['timestamp'] = pd.to_datetime(df_predictions['timestamp'])
        daily_recommendations = {}
        # Фільтруємо рекомендації, щоб показувати лише майбутні або найближчі
        # Наприклад, тільки ті, що після останнього фактичного часу
        if last_actual_data_timestamp:
            df_future_predictions = df_predictions[df_predictions['timestamp'] > last_actual_data_timestamp].copy()
        else:
            df_future_predictions = df_predictions.copy()  # Якщо немає фактичних, показуємо всі прогнози

        if not df_future_predictions.empty:
            for _, row in df_future_predictions.iterrows():
                day_str = row['timestamp'].strftime('%Y-%m-%d')
                if day_str not in daily_recommendations:
                    daily_recommendations[day_str] = []
                daily_recommendations[day_str].append(
                    f"{row['timestamp'].strftime('%H:%M')}: {row['recommendation']} (Прогноз: {row['predicted_price']:.2f} EUR/MWh)"
                )

            # Сортуємо дні для послідовного відображення
            for day_key in sorted(daily_recommendations.keys()):
                recommendations.append({'day': day_key, 'recs': daily_recommendations[day_key]})

    context = {
        'labels': json.dumps(labels),
        'prices_actual': json.dumps(prices_actual),
        'prices_predicted': json.dumps(prices_predicted),
        'demand': json.dumps(demand),
        'supply': json.dumps(supply),
        'wind_gen': json.dumps(wind_gen),
        'solar_gen': json.dumps(solar_gen),
        'temperature': json.dumps(temperature),
        'rad_direct': json.dumps(rad_direct),
        'rad_diffuse': json.dumps(rad_diffuse),
        'dashboard_filters': dashboard_filters,
        'data_period_info': f"{dashboard_filters['start_date']} - {dashboard_filters['end_date']}",
        'recommendations': recommendations
    }
    return render(request, 'core/energy_dashboard.html', context)