from django.contrib import admin
from django.urls import path
from core.views import home, login, dashboard

urlpatterns = [
    path("", home),
    path("giris/", login),
    path("panel/", dashboard),
    path("admin/", admin.site.urls),
]