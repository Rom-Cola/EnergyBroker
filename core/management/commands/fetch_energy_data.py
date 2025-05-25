import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from core.models import EnergyData
from django.utils import timezone
import os


class Command(BaseCommand):
    help = "Fetches energy data from a local CSV file and saves it to the database"

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file')

    def handle(self, *args, **options):
        csv_file_path = options['csv_file']

        if not os.path.exists(csv_file_path):
            raise CommandError(f"File not found at: {csv_file_path}")

        try:
            data = pd.read_csv(csv_file_path)
        except Exception as e:
            raise CommandError(f"Error reading CSV file: {e}")

        # Перевірка наявності необхідних стовпців
        required_columns = ['utc_timestamp', 'Price_Day_Ahead_EUR_per_MWh', 'Load_MW', 'Wind_Generation_MW',
                            'Solar_Generation_MW']
        for col in required_columns:
            if col not in data.columns:
                raise CommandError(
                    f"Required column '{col}' not found in CSV file. Available columns: {data.columns.tolist()}")

        # Замість 'Load_MW' та 'Wind_Generation_MW', 'Solar_Generation_MW' може бути
        # 'Demand', 'Wind_Forecast_MW', 'Solar_Forecast_MW' тощо, залежить від вашого файлу.
        # Якщо у вашому CSV немає 'Supply', 'Wind_Generation_MW' чи 'Solar_Generation_MW',
        # вам потрібно буде відповідно адаптувати модель EnergyData і цей код.
        # Наприклад, якщо 'Supply' відсутній, можете зробити його Optional.

        try:
            for index, row in data.iterrows():
                # Перетворення timestamp
                timestamp_str = str(row['utc_timestamp'])
                timestamp = pd.to_datetime(timestamp_str, utc=True)

                # Забезпечення наявності всіх необхідних даних перед створенням об'єкта
                # Використовуйте .get(col, default_value) для необов'язкових полів
                # або переконайтеся, що дані присутні.

                # Приклад обробки потенційних NaN або відсутніх даних
                price_val = row['Price_Day_Ahead_EUR_per_MWh'] if pd.notna(row['Price_Day_Ahead_EUR_per_MWh']) else 0.0
                demand_val = row['Load_MW'] if pd.notna(row['Load_MW']) else 0.0

                # Якщо у вашому synthetic_energy_data.csv немає 'Supply'
                # то потрібно або додати його в генератор, або зробити поле 'supply' в моделі EnergyData nullable
                # та надати йому default=None або обробити NaN
                supply_val = row['Supply_MW'] if 'Supply_MW' in data.columns and pd.notna(row['Supply_MW']) else 0.0

                temp_val = row['temperature'] if 'temperature' in data.columns and pd.notna(
                    row['temperature']) else None
                wind_gen_val = row['Wind_Generation_MW'] if 'Wind_Generation_MW' in data.columns and pd.notna(
                    row['Wind_Generation_MW']) else 0.0
                solar_gen_val = row['Solar_Generation_MW'] if 'Solar_Generation_MW' in data.columns and pd.notna(
                    row['Solar_Generation_MW']) else 0.0

                EnergyData.objects.create(
                    timestamp=timestamp,
                    price=price_val,
                    demand=demand_val,
                    supply=supply_val,  # Перевірте, чи є це поле у вашому CSV!
                    temperature=temp_val,
                    wind_generation=wind_gen_val,
                    solar_generation=solar_gen_val,
                )
            self.stdout.write(self.style.SUCCESS(f'Successfully imported data from {csv_file_path}'))

        except Exception as e:
            # Додайте більше деталей для налагодження
            self.stdout.write(self.style.ERROR(f"Error processing and saving data at row {index}: {e}"))
            raise CommandError(f"Error processing and saving data: {e}")