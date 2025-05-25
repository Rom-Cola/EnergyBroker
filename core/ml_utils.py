import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from xgboost import XGBRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error
import joblib
from datetime import datetime, timedelta
import os

# Налаштування (можна винести в settings.py або окремий конфіг)
MODEL_PATH = 'price_prediction_model.pkl'  # Шлях для збереження моделі
RECOMMENDATION_THRESHOLD_BUY = 0.98  # Купувати, якщо прогнозована ціна на 2% нижче середньої за 24 години
RECOMMENDATION_THRESHOLD_SELL = 1.02  # Продавати, якщо прогнозована ціна на 2% вище середньої за 24 години


def create_features(df):
    """
    Створює додаткові ознаки з часового штампу та існуючих даних.
    """
    df_copy = df.copy()

    df_copy['hour'] = df_copy['timestamp'].dt.hour
    df_copy['dayofweek'] = df_copy['timestamp'].dt.dayofweek
    df_copy['dayofyear'] = df_copy['timestamp'].dt.dayofyear
    df_copy['weekofyear'] = df_copy['timestamp'].dt.isocalendar().week.astype(int)
    df_copy['month'] = df_copy['timestamp'].dt.month
    df_copy['quarter'] = df_copy['timestamp'].dt.quarter
    df_copy['year'] = df_copy['timestamp'].dt.year

    # Лагові ознаки (ціна, попит, генерація за попередні години)
    # ВИПРАВЛЕНО: замінено .fillna(method='bfill') на .bfill()
    df_copy['price_lag1'] = df_copy['price'].shift(1).bfill()
    df_copy['demand_lag1'] = df_copy['demand'].shift(1).bfill()
    df_copy['wind_gen_lag1'] = df_copy['wind_generation'].shift(1).bfill()
    df_copy['solar_gen_lag1'] = df_copy['solar_generation'].shift(1).bfill()

    # Ковзні середні (наприклад, середня ціна за останні 24 години)
    # ВИПРАВЛЕНО: замінено .fillna(method='bfill') на .bfill()
    df_copy['price_rolling_mean_24h'] = df_copy['price'].rolling(window=24).mean().bfill()
    df_copy['demand_rolling_mean_24h'] = df_copy['demand'].rolling(window=24).mean().bfill()
    df_copy['wind_gen_rolling_mean_24h'] = df_copy['wind_generation'].rolling(window=24).mean().bfill()
    df_copy['solar_gen_rolling_mean_24h'] = df_copy['solar_generation'].rolling(window=24).mean().bfill()

    df_copy['is_peak_hour'] = ((df_copy['hour'] >= 7) & (df_copy['hour'] <= 22)).astype(int)
    df_copy['is_weekend'] = (df_copy['dayofweek'] >= 5).astype(int)

    return df_copy


def train_model(df_full_data):
    """
    Навчає модель градієнтного бустингу (XGBoost) та зберігає її.
    Приймає повний датафрейм, розділяє його, створює ознаки.
    """
    df_features = create_features(df_full_data.copy())

    features = [
        'hour', 'dayofweek', 'dayofyear', 'weekofyear', 'month', 'quarter', 'year',
        'demand', 'temperature', 'wind_generation', 'solar_generation',
        'radiation_direct_horizontal', 'radiation_diffuse_horizontal',
        'price_lag1', 'demand_lag1', 'wind_gen_lag1', 'solar_gen_lag1',
        'price_rolling_mean_24h', 'demand_rolling_mean_24h', 'wind_gen_rolling_mean_24h', 'solar_gen_rolling_mean_24h',
        'is_peak_hour', 'is_weekend'
    ]
    target = 'price'

    missing_features_in_df = [f for f in features if f not in df_features.columns]
    if missing_features_in_df:
        raise ValueError(
            f"Відсутні необхідні ознаки для навчання моделі: {missing_features_in_df}. Доступні: {df_features.columns.tolist()}")

    X = df_features[features]
    y = df_features[target]

    if df_features.empty:
        raise ValueError("DataFrame порожній після створення ознак.")

    df_features.sort_values(by='timestamp', inplace=True)

    split_point_date = df_features['timestamp'].max() - timedelta(days=30)

    X_train = X[df_features['timestamp'] <= split_point_date]
    y_train = y[df_features['timestamp'] <= split_point_date]
    X_test = X[df_features['timestamp'] > split_point_date]
    y_test = y[df_features['timestamp'] > split_point_date]

    if X_train.empty or y_train.empty:
        raise ValueError(
            f"Тренувальний набір даних порожній. Перевірте діапазон даних. Max timestamp: {df_features['timestamp'].max()}, Split date: {split_point_date}")
    if X_test.empty or y_test.empty:
        raise ValueError(
            f"Тестовий набір даних порожній. Перевірте діапазон даних. Max timestamp: {df_features['timestamp'].max()}, Split date: {split_point_date}")

    model = XGBRegressor(
        objective='reg:squarederror',
        n_estimators=1000,
        learning_rate=0.05,
        early_stopping_rounds=50,
        eval_metric='rmse',
        n_jobs=-1,
        random_state=42
    )

    model.fit(X_train, y_train,
              eval_set=[(X_test, y_test)],
              verbose=False)

    y_pred = model.predict(X_test)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mae = mean_absolute_error(y_test, y_pred)

    print(f"\n--- Оцінка моделі на тестових даних ---")
    print(f"Розмір тренувального набору: {len(X_train)}")
    print(f"Розмір тестового набору: {len(X_test)}")
    print(f"RMSE (Root Mean Squared Error): {rmse:.2f}")
    print(f"MAE (Mean Absolute Error): {mae:.2f}")

    joblib.dump(model, MODEL_PATH)
    print(f"Модель успішно збережена за шляхом: {MODEL_PATH}")

    return model, features


def load_model():
    """
    Завантажує збережену модель машинного навчання.
    """
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(
            f"Модель не знайдена за шляхом: {MODEL_PATH}. Будь ласка, спочатку натренуйте модель за допомогою 'python manage.py train_predict_model --retrain'.")

    model = joblib.load(MODEL_PATH)
    print(f"Модель успішно завантажена з: {MODEL_PATH}")
    return model


def predict_prices(model, df_to_predict_raw, features):
    """
    Генерує прогнозовані ціни для нових даних.
    Очікує сирий DataFrame з timestamp та основними даними.
    """
    df_to_predict_features = create_features(df_to_predict_raw.copy())

    missing_features_in_df = [f for f in features if f not in df_to_predict_features.columns]
    if missing_features_in_df:
        raise ValueError(
            f"Відсутні необхідні ознаки для прогнозування: {missing_features_in_df}. Доступні: {df_to_predict_features.columns.tolist()}")

    X_predict = df_to_predict_features[features]
    predictions = model.predict(X_predict)

    df_to_predict_features['predicted_price'] = predictions
    return df_to_predict_features[['timestamp', 'price', 'predicted_price', 'price_rolling_mean_24h']]


def generate_recommendations(df_predictions):
    """
    Генерує рекомендації (купівля/продаж) на основі прогнозованих цін.
    """
    recommendations = []
    df_predictions_filtered = df_predictions.dropna(subset=['price_rolling_mean_24h'])

    for index, row in df_predictions_filtered.iterrows():
        rec_text = "Нейтрально"
        if row['predicted_price'] < row['price_rolling_mean_24h'] * RECOMMENDATION_THRESHOLD_BUY:
            rec_text = "КУПУВАТИ"
        elif row['predicted_price'] > row['price_rolling_mean_24h'] * RECOMMENDATION_THRESHOLD_SELL:
            rec_text = "ПРОДАВАТИ"

        recommendations.append({
            'timestamp': row['timestamp'],
            'predicted_price': row['predicted_price'],
            'actual_price': row['price'],
            'recommendation': rec_text
        })
    return recommendations