from django.contrib import admin
from .models import EnergyData

@admin.register(EnergyData)
class EnergyDataAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'price', 'demand', 'supply', 'temperature', 'wind_generation', 'solar_generation')
    list_filter = ('timestamp',)
    search_fields = ('timestamp',)
    date_hierarchy = 'timestamp'