from django.contrib import admin
from django.urls import path
from core.views import home, login_view, dashboard

urlpatterns = [
    path("", home, name="home"),
    path("giris/", login_view, name="login"),
    path("panel/", dashboard, name="dashboard"),
    path("admin/", admin.site.urls),
]