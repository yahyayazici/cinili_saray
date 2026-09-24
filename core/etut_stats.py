"""Etüt ve sınıf ortalamaları için yardımcı sorgular."""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Avg, Count, QuerySet

from core.models import Deneme, Konu, KonuSonuc, Sinif, Talebe


def _avg_or_none(value) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(round(float(value), 2)))


def etut_konu_ozeti(etut, deneme: Deneme | None = None) -> list[dict]:
    """Etütteki talebelerin konu bazlı ortalamaları.

    Kazanım Excel'lerinden gelen konular burada listelenir.
    deneme verilirse sadece o denemeye bakar; yoksa tüm denemelerin ortalaması.
    """
    talebe_ids = list(etut.talebeler.values_list("id", flat=True))
    if not talebe_ids:
        return []

    qs = KonuSonuc.objects.filter(
        talebe_id__in=talebe_ids,
        yuzde__isnull=False,
    )
    if deneme is not None:
        qs = qs.filter(deneme=deneme)

    rows = (
        qs.values("konu_id", "konu__ad", "konu__ders__ad")
        .annotate(
            ortalama=Avg("yuzde"),
            katilim=Count("id"),
            talebe_sayisi=Count("talebe_id", distinct=True),
        )
        .order_by("konu__ders__ad", "konu__ad")
    )

    return [
        {
            "konu_id": row["konu_id"],
            "ders": row["konu__ders__ad"],
            "konu": row["konu__ad"],
            "ortalama": _avg_or_none(row["ortalama"]),
            "katilim": row["katilim"],
            "talebe_sayisi": row["talebe_sayisi"],
        }
        for row in rows
    ]


def etut_konu_talebe_satirlari(
    etut,
    konu: Konu,
    deneme: Deneme,
) -> list[dict]:
    """Seçili denemede etüt talebelerinin konu skorları."""
    talebe_ids = list(etut.talebeler.values_list("id", flat=True))
    sonuclar = {
        s.talebe_id: s
        for s in KonuSonuc.objects.filter(
            deneme=deneme,
            konu=konu,
            talebe_id__in=talebe_ids,
        ).select_related("talebe", "talebe__sinif")
    }

    satirlar = []
    yuzdeler = []
    for talebe in etut.talebeler.select_related("sinif").order_by("ad_soyad"):
        sonuc = sonuclar.get(talebe.id)
        yuzde = sonuc.yuzde if sonuc else None
        if yuzde is not None:
            yuzdeler.append(float(yuzde))
        satirlar.append(
            {
                "talebe": talebe,
                "yuzde": yuzde,
                "net_dogru": sonuc.net_dogru if sonuc else None,
                "net_toplam": sonuc.net_toplam if sonuc else None,
            }
        )

    ortalama = (
        _avg_or_none(sum(yuzdeler) / len(yuzdeler)) if yuzdeler else None
    )
    return satirlar, ortalama


def sinif_raporu(deneme: Deneme, sinif: Sinif | None = None) -> list[dict]:
    """Deneme için sınıf (veya tüm sınıflar) konu ortalamaları."""
    qs: QuerySet = KonuSonuc.objects.filter(
        deneme=deneme,
        yuzde__isnull=False,
    )
    if sinif is not None:
        qs = qs.filter(talebe__sinif=sinif)

    rows = (
        qs.values("konu_id", "konu__ad", "konu__ders__ad")
        .annotate(
            ortalama=Avg("yuzde"),
            talebe_sayisi=Count("talebe_id", distinct=True),
        )
        .order_by("konu__ders__ad", "konu__ad")
    )
    return [
        {
            "konu_id": row["konu_id"],
            "ders": row["konu__ders__ad"],
            "konu": row["konu__ad"],
            "ortalama": _avg_or_none(row["ortalama"]),
            "talebe_sayisi": row["talebe_sayisi"],
        }
        for row in rows
    ]


def sinif_konu_karsilastirma(
    deneme: Deneme,
    konu: Konu,
    etut,
    sinif: Sinif | None = None,
) -> dict:
    """Aynı konu için etüt ortalaması + sınıf ortalaması yan yana."""
    talebe_ids = list(etut.talebeler.values_list("id", flat=True))

    etut_avg = KonuSonuc.objects.filter(
        deneme=deneme,
        konu=konu,
        talebe_id__in=talebe_ids,
        yuzde__isnull=False,
    ).aggregate(v=Avg("yuzde"))["v"]

    sinif_qs = KonuSonuc.objects.filter(
        deneme=deneme,
        konu=konu,
        yuzde__isnull=False,
    )
    if sinif is not None:
        sinif_qs = sinif_qs.filter(talebe__sinif=sinif)
    else:
        # Etütteki talebelerin sınıflarına bak
        sinif_ids = (
            Talebe.objects.filter(id__in=talebe_ids)
            .values_list("sinif_id", flat=True)
            .distinct()
        )
        sinif_qs = sinif_qs.filter(talebe__sinif_id__in=sinif_ids)

    sinif_avg = sinif_qs.aggregate(v=Avg("yuzde"))["v"]
    return {
        "etut_ortalama": _avg_or_none(etut_avg),
        "sinif_ortalama": _avg_or_none(sinif_avg),
    }
