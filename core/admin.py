from django.contrib import admin

from core.models import Deneme, Ders, Konu, KonuSonuc, Sinif, Talebe


@admin.register(Sinif)
class SinifAdmin(admin.ModelAdmin):
    search_fields = ("ad",)


@admin.register(Talebe)
class TalebeAdmin(admin.ModelAdmin):
    list_display = ("ad_soyad", "sinif")
    list_filter = ("sinif",)
    search_fields = ("ad_soyad",)


@admin.register(Ders)
class DersAdmin(admin.ModelAdmin):
    search_fields = ("ad",)


@admin.register(Konu)
class KonuAdmin(admin.ModelAdmin):
    list_display = ("ad", "ders")
    list_filter = ("ders",)
    search_fields = ("ad", "ders__ad")


@admin.register(Deneme)
class DenemeAdmin(admin.ModelAdmin):
    list_display = ("ad", "tarih", "kaynak_dosya", "olusturulma")
    list_filter = ("tarih",)
    search_fields = ("ad",)


@admin.register(KonuSonuc)
class KonuSonucAdmin(admin.ModelAdmin):
    list_display = ("deneme", "talebe", "konu", "yuzde", "net_dogru", "net_toplam")
    list_filter = ("deneme", "konu__ders")
    search_fields = ("talebe__ad_soyad", "konu__ad")
