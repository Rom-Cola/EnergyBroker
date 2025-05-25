import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def generate_synthetic_energy_data(start_date_str, end_date_str):
    """
    Generates a synthetic CSV file with energy data.
    """
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d')

    date_rng = pd.date_range(start=start_date, end=end_date, freq='H', tz='Europe/Kiev') # Додаємо часовий пояс

    data = {
        'utc_timestamp': date_rng.strftime('%Y-%m-%dT%H:%M:%S%z'), # Формат ISO 8601 з часовим поясом
        'Price_Day_Ahead_EUR_per_MWh': np.random.uniform(low=30, high=150, size=len(date_rng)).round(2),
        'Load_MW': np.random.uniform(low=10000, high=50000, size=len(date_rng)).round(2),
        'Supply_MW': np.random.uniform(low=12000, high=52000, size=len(date_rng)).round(2), # Додано supply
        'Wind_Generation_MW': np.random.randint(low=0, high=10000, size=len(date_rng)),
        'Solar_Generation_MW': np.random.randint(low=0, high=5000, size=len(date_rng)),
        'temperature': np.random.uniform(low=-10, high=35, size=len(date_rng)).round(1),
    }

    df = pd.DataFrame(data)
    return df

# Налаштування
start_date = '2023-01-01'
end_date = '2023-01-31' # Місяць даних для тестування

# Генеруємо дані
synthetic_data = generate_synthetic_energy_data(start_date, end_date)

# Зберігаємо у CSV-файл у кореневій директорії проєкту
synthetic_data.to_csv('synthetic_energy_data.csv', index=False)

print("Synthetic energy data generated in 'synthetic_energy_data.csv'")