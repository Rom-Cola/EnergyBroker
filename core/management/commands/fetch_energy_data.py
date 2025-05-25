import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from core.models import EnergyData
from django.utils import timezone
import os


class Command(BaseCommand):
    help = "Fetches energy data from the merged CSV file for DK_1 market and saves it to the database"

    def add_arguments(self, parser):
        parser.add_argument('merged_csv_file', type=str,
                            help='Path to the merged CSV file (e.g., merged_energy_weather_data.csv)')

    def handle(self, *args, **options):
        merged_csv_file_path = options['merged_csv_file']

        if not os.path.exists(merged_csv_file_path):
            raise CommandError(f"File not found at: {merged_csv_file_path}")

        try:
            data = pd.read_csv(merged_csv_file_path)
            self.stdout.write(self.style.SUCCESS(f"Successfully loaded merged data from {merged_csv_file_path}"))
        except Exception as e:
            raise CommandError(f"Error reading merged CSV file: {e}")

        # --- Ключові стовпці для Данії, зона 1 (DK_1) ---
        # ЦІ НАЗВИ ПОВНІСТЮ ВІДПОВІДАЮТЬ ВАШОМУ ВИВОДУ З ВАЛІДАЦІЇ ОБ'ЄДНАНОГО ДАТАСЕТУ

        TIMESTAMP_COL = 'utc_timestamp'
        PRICE_COL = 'DK_1_price_day_ahead'
        DEMAND_COL = 'DK_1_load_actual_entsoe_transparency'

        # Ми визначили, що прямого стовпця 'Supply' у цьому датасеті немає для DK_1.
        # Залишаємо None, якщо немає відповідного стовпця для пропозиції.
        SUPPLY_COL_NAME_IN_CSV = None

        WIND_GEN_COL = 'DK_1_wind_generation_actual'
        SOLAR_GEN_COL = 'DK_1_solar_generation_actual'

        # Погодні стовпці (перейменовані під час об'єднання скриптом check_and_save_merged_data.py)
        TEMP_COL = 'temperature'
        RAD_DIRECT_COL = 'radiation_direct_horizontal'
        RAD_DIFFUSE_COL = 'radiation_diffuse_horizontal'

        # Перелік усіх стовпців, які ми плануємо використовувати.
        # Всі вони повинні бути присутні у DataFrame.
        columns_to_check = [
            TIMESTAMP_COL, PRICE_COL, DEMAND_COL, WIND_GEN_COL, SOLAR_GEN_COL,
            TEMP_COL, RAD_DIRECT_COL, RAD_DIFFUSE_COL
        ]
        if SUPPLY_COL_NAME_IN_CSV:  # Додаємо тільки якщо SUPPLY_COL_NAME_IN_CSV не None
            columns_to_check.append(SUPPLY_COL_NAME_IN_CSV)

        for col in columns_to_check:
            if col not in data.columns:
                raise CommandError(
                    f"Required column '{col}' not found in the merged CSV file. "
                    f"Please verify your column names. Available columns: {data.columns.tolist()}"
                )

        self.stdout.write(self.style.NOTICE(f"Starting data import for DK_1 market to EnergyData model..."))

        try:
            # Очистимо існуючі дані, щоб уникнути дублікатів при повторному імпорті.
            # УВАГА: Це видаляє ВСІ існуючі дані EnergyData перед імпортом!
            # Закомментуйте цей рядок, якщо ви хочете додавати дані, а не перезаписувати.
            EnergyData.objects.all().delete()  # Розкоментуйте, якщо хочете очищати базу перед імпортом
            self.stdout.write(self.style.WARNING("Existing EnergyData records deleted (if uncommented)."))

            # Видаляємо рядки з пропущеними значеннями в ключових стовпцях,
            # оскільки їх дуже мало для DK_1 (0.00% - 0.03%).
            initial_rows = len(data)
            data.dropna(
                subset=[PRICE_COL, DEMAND_COL, WIND_GEN_COL, SOLAR_GEN_COL, TEMP_COL, RAD_DIRECT_COL, RAD_DIFFUSE_COL],
                inplace=True)
            rows_after_dropna = len(data)
            if initial_rows - rows_after_dropna > 0:
                self.stdout.write(self.style.NOTICE(
                    f"Removed {initial_rows - rows_after_dropna} rows with NaN in key columns. Remaining rows: {rows_after_dropna}"))

            count = 0
            for index, row in data.iterrows():
                try:
                    timestamp = pd.to_datetime(row[TIMESTAMP_COL], utc=True)

                    price_val = row[PRICE_COL]
                    demand_val = row[DEMAND_COL]
                    wind_gen_val = row[WIND_GEN_COL]
                    solar_gen_val = row[SOLAR_GEN_COL]

                    # Якщо SUPPLY_COL_NAME_IN_CSV не задано, supply_val буде None, що дозволено моделлю.
                    supply_val = row[SUPPLY_COL_NAME_IN_CSV] if SUPPLY_COL_NAME_IN_CSV and pd.notna(
                        row[SUPPLY_COL_NAME_IN_CSV]) else None

                    temp_val = row[TEMP_COL]
                    rad_direct_val = row[RAD_DIRECT_COL]
                    rad_diffuse_val = row[RAD_DIFFUSE_COL]

                    EnergyData.objects.create(
                        timestamp=timestamp,
                        price=price_val,
                        demand=demand_val,
                        supply=supply_val,
                        temperature=temp_val,
                        wind_generation=wind_gen_val,
                        solar_generation=solar_gen_val,
                        radiation_direct_horizontal=rad_direct_val,
                        radiation_diffuse_horizontal=rad_diffuse_val,
                    )
                    count += 1
                except Exception as row_e:
                    # Логуємо помилку і пропускаємо рядок, щоб імпорт продовжився
                    self.stdout.write(
                        self.style.ERROR(f"Error importing row {index} ({row.get(TIMESTAMP_COL, 'N/A')}): {row_e}"))
                    continue

            self.stdout.write(self.style.SUCCESS(f'Successfully imported {count} records into EnergyData model.'))

        except Exception as e:
            raise CommandError(f"Fatal error during data processing and saving: {e}")