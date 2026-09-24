from django.contrib import admin
from django.urls import path
from core.views import (
    home,
    login_view,
    dashboard,
    akademik_takip,
    deneme_yukle,
    deneme_detay,
    konu_listesi,
)

urlpatterns = [
    path("", home, name="home"),
    path("giris/", login_view, name="login"),
    path("panel/", dashboard, name="dashboard"),
    path("panel/akademik/", akademik_takip, name="akademik_takip"),
    path("panel/akademik/yukle/", deneme_yukle, name="deneme_yukle"),
    path("panel/akademik/deneme/<int:deneme_id>/", deneme_detay, name="deneme_detay"),
    path("panel/akademik/konular/", konu_listesi, name="konu_listesi"),
    path("admin/", admin.site.urls),
]
