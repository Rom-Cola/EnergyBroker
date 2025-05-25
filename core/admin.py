from django.contrib import admin
from .models import EnergyData, PricePrediction # Додано PricePrediction

@admin.register(EnergyData)
class EnergyDataAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'price', 'demand', 'supply', 'temperature',
                    'wind_generation', 'solar_generation',
                    'radiation_direct_horizontal', 'radiation_diffuse_horizontal')
    list_filter = ('timestamp',)
    search_fields = ('timestamp',)
    date_hierarchy = 'timestamp'
    list_per_page = 25

@admin.register(PricePrediction) # Реєструємо нову модель
class PricePredictionAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'predicted_price', 'actual_price', 'recommendation')
    list_filter = ('timestamp',)
    search_fields = ('timestamp',)
    date_hierarchy = 'timestamp'
    list_per_page = 25