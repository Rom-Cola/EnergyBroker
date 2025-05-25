from django.db import models

class EnergyData(models.Model):
    timestamp = models.DateTimeField()
    price = models.FloatField()
    demand = models.FloatField()
    supply = models.FloatField(null=True, blank=True)
    temperature = models.FloatField(null=True, blank=True)
    wind_generation = models.FloatField(null=True, blank=True)
    solar_generation = models.FloatField(null=True, blank=True)
    radiation_direct_horizontal = models.FloatField(null=True, blank=True)
    radiation_diffuse_horizontal = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"{self.timestamp.strftime('%Y-%m-%d %H:%M')} - Price: {self.price} EUR/MWh"

    class Meta:
        ordering = ['timestamp']
        # Додайте індекс на timestamp, якщо працюєте з дуже великими даними
        # indexes = [models.Index(fields=['timestamp'])]

class PricePrediction(models.Model):
    timestamp = models.DateTimeField(unique=True) # Кожен прогноз має бути унікальним за часом
    predicted_price = models.FloatField()
    actual_price = models.FloatField(null=True, blank=True) # Для порівняння з фактичною ціною, якщо доступно
    recommendation = models.CharField(max_length=255, blank=True, null=True) # Рекомендація (купувати/продавати)

    def __str__(self):
        return f"Прогноз на {self.timestamp.strftime('%Y-%m-%d %H:%M')}: {self.predicted_price:.2f} EUR/MWh ({self.recommendation})"

    class Meta:
        ordering = ['timestamp']