from django.db import models

class EnergyData(models.Model):
    timestamp = models.DateTimeField()
    price = models.FloatField()
    demand = models.FloatField()
    supply = models.FloatField() # Припускаємо, що це поле також є
    temperature = models.FloatField(null=True, blank=True)
    wind_generation = models.FloatField(null=True, blank=True)
    solar_generation = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"{self.timestamp.strftime('%Y-%m-%d %H:%M')} - Price: {self.price} EUR/MWh"

    class Meta:
        ordering = ['timestamp']