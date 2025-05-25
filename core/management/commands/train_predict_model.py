import pandas as pd
import numpy as np
from django.core.management.base import BaseCommand, CommandError
from core.models import EnergyData, PricePrediction
from core.ml_utils import train_model, load_model, predict_prices, generate_recommendations, MODEL_PATH, create_features
from django.utils import timezone
from datetime import timedelta, datetime


class Command(BaseCommand):
    help = "Trains the energy price prediction model, generates predictions, and saves them."

    def add_arguments(self, parser):
        parser.add_argument(
            '--retrain',
            action='store_true',
            help='Force retraining of the model even if one exists.',
        )
        parser.add_argument(
            '--predict-period-days',
            type=int,
            default=7,  # Прогнозуємо на 7 днів вперед після останньої доступної дати
            help='Number of days to predict into the future from the last available data point.',
        )

    def handle(self, *args, **options):
        retrain = options['retrain']
        predict_period_days = options['predict_period_days']

        self.stdout.write(self.style.NOTICE("--- Starting ML Model Operations ---"))

        # --- 1. Завантаження даних з бази даних ---
        self.stdout.write(self.style.NOTICE("Loading data from EnergyData model..."))
        energy_data_qs = EnergyData.objects.all().order_by('timestamp')
        if not energy_data_qs.exists():
            raise CommandError("No data found in EnergyData model. Please import data first.")

        df_full = pd.DataFrame(list(energy_data_qs.values()))
        df_full['timestamp'] = pd.to_datetime(df_full['timestamp'])

        initial_rows_ml = len(df_full)
        ml_relevant_cols = [
            'price', 'demand', 'temperature', 'wind_generation', 'solar_generation',
            'radiation_direct_horizontal', 'radiation_diffuse_horizontal'
        ]
        df_full.dropna(subset=ml_relevant_cols, inplace=True)
        rows_after_dropna_ml = len(df_full)
        if initial_rows_ml - rows_after_dropna_ml > 0:
            self.stdout.write(self.style.WARNING(
                f"Removed {initial_rows_ml - rows_after_dropna_ml} rows with NaN in ML-relevant columns."))

        if df_full.empty:
            raise CommandError("No valid data remaining after cleaning for ML training.")

        self.stdout.write(self.style.SUCCESS(f"Successfully loaded {len(df_full)} records for ML."))

        # --- 2. Навчання або завантаження моделі ---
        model = None
        features = None
        try:
            if retrain:
                self.stdout.write(self.style.WARNING("Retraining model as requested..."))
                model, features = train_model(df_full)
            else:
                self.stdout.write(self.style.NOTICE("Attempting to load existing model..."))
                model = load_model()
                # Перестворюємо ознаки для визначення features
                temp_df_for_features = create_features(df_full.copy())
                # Використовуємо той самий список features, що і в train_model
                features = [
                    'hour', 'dayofweek', 'dayofyear', 'weekofyear', 'month', 'quarter', 'year',
                    'demand', 'temperature', 'wind_generation', 'solar_generation',
                    'radiation_direct_horizontal', 'radiation_diffuse_horizontal',
                    'price_lag1', 'demand_lag1', 'wind_gen_lag1', 'solar_gen_lag1',
                    'price_rolling_mean_24h', 'demand_rolling_mean_24h', 'wind_gen_rolling_mean_24h',
                    'solar_gen_rolling_mean_24h',
                    'is_peak_hour', 'is_weekend'
                ]
                self.stdout.write(self.style.SUCCESS("Model loaded successfully."))

        except FileNotFoundError:
            self.stdout.write(self.style.WARNING("Model not found. Training new model..."))
            model, features = train_model(df_full)
        except Exception as e:
            raise CommandError(f"Error loading or training model: {e}")

        # --- 3. Генерація прогнозів ---
        self.stdout.write(self.style.NOTICE(f"Generating predictions for the next {predict_period_days} days..."))

        last_timestamp_actual = df_full['timestamp'].max()

        # Створюємо майбутні часові мітки для прогнозування
        future_timestamps = pd.date_range(
            start=last_timestamp_actual + timedelta(hours=1),  # Починаємо з години після останніх фактичних даних
            periods=predict_period_days * 24,  # Кількість годин для прогнозування
            freq='h',  # Годинна частота
            tz='UTC'
        )

        # Створюємо DataFrame для майбутніх даних, заповнюючи відомі ознаки
        # Тут ми робимо спрощення: майбутні погодні дані та попит дорівнюють останнім відомим фактичним значенням.
        # У реальному проекті тут потрібні були б прогнози.
        last_row_actual = df_full.iloc[-1]

        df_future_data = pd.DataFrame({
            'timestamp': future_timestamps,
            'price': np.nan,  # Цільова змінна, яку прогнозуємо
            'demand': last_row_actual['demand'],
            'temperature': last_row_actual['temperature'],
            'wind_generation': last_row_actual['wind_generation'],
            'solar_generation': last_row_actual['solar_generation'],
            'radiation_direct_horizontal': last_row_actual['radiation_direct_horizontal'],
            'radiation_diffuse_horizontal': last_row_actual['radiation_diffuse_horizontal'],
            'supply': last_row_actual['supply'] if 'supply' in last_row_actual else np.nan,  # Якщо supply є, включаємо
        })

        # --- Важливо: Об'єднуємо останні N фактичних рядків з майбутніми для розрахунку лагів та ковзних середніх ---
        # Кількість рядків для tail має бути принаймні window (24 для rolling mean) + max_lag (1 для lag1)
        # Або просто візьміть достатньо велику кількість, щоб перекрити всі залежності
        # Для rolling(window=24) потрібно 24 попередні точки.
        # Для predict_prices, create_features робить .dropna()
        # Тому потрібно, щоб df_for_prediction_features мав достатньо повних даних на початку.

        # Візьмемо останній місяць фактичних даних для допомоги в розрахунку лагів
        df_recent_actual = df_full[df_full['timestamp'] >= (df_full['timestamp'].max() - timedelta(days=30))].copy()

        # Об'єднуємо актуальні дані з майбутніми для створення ознак
        # Це дозволяє лаговим ознакам "перетікати" з фактичних даних до прогнозованих
        df_for_prediction_features_raw = pd.concat([df_recent_actual, df_future_data], ignore_index=True)
        df_for_prediction_features_raw.sort_values(by='timestamp', inplace=True)  # Важливо для лагів

        # Генеруємо прогнози для об'єднаного датафрейму
        df_predictions_with_features = predict_prices(model, df_for_prediction_features_raw, features)

        # Вибираємо тільки ті прогнози, які стосуються МАЙБУТНІХ часових міток (future_timestamps)
        # Або ті, що знаходяться після останньої фактичної дати
        df_final_predictions = df_predictions_with_features[
            df_predictions_with_features['timestamp'] > last_timestamp_actual
            ].copy()

        if df_final_predictions.empty:
            self.stdout.write(self.style.WARNING(
                "No future predictions generated. Check date ranges or data availability in df_full after cleaning."))
            return

        # --- 4. Генерація рекомендацій ---
        self.stdout.write(self.style.NOTICE("Generating recommendations..."))
        # Для рекомендацій потрібні price_rolling_mean_24h, які є NaN на початку прогнозу.
        # Ми їх залишаємо None в базі даних, але для рекомендацій може знадобитися імпутація.
        # generate_recommendations вже використовує dropna для price_rolling_mean_24h,
        # тому для перших 24 годин прогнозу їх не буде.

        recommendations = generate_recommendations(df_final_predictions)

        # --- 5. Збереження прогнозів та рекомендацій в базу даних ---
        self.stdout.write(self.style.NOTICE("Saving predictions and recommendations to database..."))

        PricePrediction.objects.all().delete()
        self.stdout.write(self.style.WARNING("Existing PricePrediction records deleted."))

        saved_count = 0
        for rec in recommendations:
            PricePrediction.objects.create(
                timestamp=rec['timestamp'],
                predicted_price=rec['predicted_price'],
                actual_price=rec['actual_price'] if pd.notna(rec['actual_price']) else None,
                recommendation=rec['recommendation']
            )
            saved_count += 1

        self.stdout.write(self.style.SUCCESS(f"Successfully saved {saved_count} predictions and recommendations."))

        self.stdout.write(self.style.NOTICE("--- ML Model Operations Completed ---"))