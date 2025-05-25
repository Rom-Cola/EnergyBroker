from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('core/', include('core.urls')), # Підключаємо URL-и з застосунку 'core'
    path('api/', include('api.urls')),   # Підключаємо URL-и з застосунку 'api'
]