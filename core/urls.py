from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('energy-list/', views.energy_list, name='energy_list'),
    path('energy-dashboard/', views.energy_dashboard, name='energy_dashboard'),
]