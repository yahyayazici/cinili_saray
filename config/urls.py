from django.contrib import admin
from django.urls import path
from core.views import (
    home,
    login_view,
    dashboard,
    akademik_takip,
    deneme_yukle,
    deneme_detay,
    deneme_sinif_raporu,
    konu_listesi,
    etut_panel,
    etut_detay,
    etut_konu_detay,
)

urlpatterns = [
    path("", home, name="home"),
    path("giris/", login_view, name="login"),
    path("panel/", dashboard, name="dashboard"),
    path("panel/akademik/", akademik_takip, name="akademik_takip"),
    path("panel/akademik/yukle/", deneme_yukle, name="deneme_yukle"),
    path("panel/akademik/deneme/<int:deneme_id>/", deneme_detay, name="deneme_detay"),
    path(
        "panel/akademik/deneme/<int:deneme_id>/sinif/",
        deneme_sinif_raporu,
        name="deneme_sinif_raporu",
    ),
    path("panel/akademik/konular/", konu_listesi, name="konu_listesi"),
    path("panel/etut/", etut_panel, name="etut_panel"),
    path("panel/etut/<int:etut_id>/", etut_detay, name="etut_detay"),
    path(
        "panel/etut/<int:etut_id>/konu/<int:konu_id>/",
        etut_konu_detay,
        name="etut_konu_detay",
    ),
    path("admin/", admin.site.urls),
]
