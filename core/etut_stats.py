"""Etüt ve sınıf ortalamaları için yardımcı sorgular."""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Avg, Count, QuerySet

from core.models import Deneme, Konu, KonuSonuc, Sinif, Talebe

ZAYIF_ESIK = Decimal("70")


def _avg_or_none(value) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(round(float(value), 2)))


def _trend(values: list[float | None]) -> str:
    clean = [v for v in values if v is not None]
    if len(clean) < 2:
        return "→"
    delta = clean[-1] - clean[-2]
    if delta >= 1.5:
        return "↑"
    if delta <= -1.5:
        return "↓"
    return "→"


def etut_konu_ozeti(etut, deneme: Deneme | None = None) -> list[dict]:
    """Etütteki talebelerin konu bazlı ortalamaları."""
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
            "zayif": (
                row["ortalama"] is not None
                and Decimal(str(row["ortalama"])) < ZAYIF_ESIK
            ),
        }
        for row in rows
    ]


def etut_konu_talebe_satirlari(
    etut,
    konu: Konu,
    deneme: Deneme,
) -> tuple[list[dict], Decimal | None]:
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
            "zayif": (
                row["ortalama"] is not None
                and Decimal(str(row["ortalama"])) < ZAYIF_ESIK
            ),
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


def etut_baskin_sinif(etut) -> Sinif | None:
    sinif_id = (
        etut.talebeler.values_list("sinif_id", flat=True).order_by().first()
    )
    if not sinif_id:
        return None
    return Sinif.objects.filter(pk=sinif_id).first()


def deneme_ortalama(
    deneme: Deneme, talebe_ids: list[int] | None = None
) -> Decimal | None:
    qs = KonuSonuc.objects.filter(deneme=deneme, yuzde__isnull=False)
    if talebe_ids is not None:
        qs = qs.filter(talebe_id__in=talebe_ids)
    return _avg_or_none(qs.aggregate(v=Avg("yuzde"))["v"])


def etut_gelisim_serisi(etut) -> dict:
    """Deneme deneme etüt + sınıf ortalama çizgisi."""
    talebe_ids = list(etut.talebeler.values_list("id", flat=True))
    sinif = etut_baskin_sinif(etut)
    denemeler = list(Deneme.objects.order_by("tarih", "id"))

    labels = []
    etut_vals: list[float | None] = []
    sinif_vals: list[float | None] = []

    for deneme in denemeler:
        labels.append(deneme.ad)
        eavg = deneme_ortalama(deneme, talebe_ids)
        etut_vals.append(float(eavg) if eavg is not None else None)
        if sinif:
            savg = deneme_ortalama(
                deneme,
                list(
                    Talebe.objects.filter(sinif=sinif).values_list(
                        "id", flat=True
                    )
                ),
            )
            sinif_vals.append(float(savg) if savg is not None else None)
        else:
            sinif_vals.append(None)

    return {
        "labels": labels,
        "etut": etut_vals,
        "sinif": sinif_vals,
        "sinif_ad": sinif.ad if sinif else None,
        "trend": _trend(etut_vals),
    }


def etut_deneme_kutulari(etut) -> list[dict]:
    """Denemelerim sayfası için kutu verisi."""
    talebe_ids = list(etut.talebeler.values_list("id", flat=True))
    sinif = etut_baskin_sinif(etut)
    sinif_ids = (
        list(Talebe.objects.filter(sinif=sinif).values_list("id", flat=True))
        if sinif
        else []
    )

    krono = list(Deneme.objects.order_by("tarih", "id"))
    etut_series = [deneme_ortalama(d, talebe_ids) for d in krono]
    series_by_id = {
        d.id: (
            float(etut_series[i]) if etut_series[i] is not None else None,
            float(etut_series[i - 1])
            if i and etut_series[i - 1] is not None
            else None,
        )
        for i, d in enumerate(krono)
    }

    kutular = []
    for deneme in Deneme.objects.order_by("-tarih", "-id"):
        etut_ort = deneme_ortalama(deneme, talebe_ids)
        sinif_ort = deneme_ortalama(deneme, sinif_ids) if sinif_ids else None
        cur, prev = series_by_id.get(deneme.id, (None, None))
        if cur is None or prev is None:
            trend = "→"
        elif cur - prev >= 1.5:
            trend = "↑"
        elif cur - prev <= -1.5:
            trend = "↓"
        else:
            trend = "→"

        zayif_sayisi = sum(
            1 for row in etut_konu_ozeti(etut, deneme=deneme) if row.get("zayif")
        )

        kutular.append(
            {
                "deneme": deneme,
                "etut_ortalama": etut_ort,
                "sinif_ortalama": sinif_ort,
                "trend": trend,
                "zayif_konu": zayif_sayisi,
            }
        )
    return kutular


def etut_dikkat(etut, limit: int = 5) -> dict:
    """Hocanın bakması gereken kısa uyarı listeleri."""
    deneme = Deneme.objects.order_by("-tarih", "-id").first()
    if deneme is None:
        return {"zayif_konular": [], "dusen_talebeler": [], "deneme": None}

    sinif = etut_baskin_sinif(etut)
    zayif = []
    for row in etut_konu_ozeti(etut, deneme=deneme):
        if row["ortalama"] is None:
            continue
        kars = sinif_konu_karsilastirma(
            deneme,
            Konu.objects.get(pk=row["konu_id"]),
            etut,
            sinif=sinif,
        )
        etut_o = kars["etut_ortalama"]
        sinif_o = kars["sinif_ortalama"]
        fark = None
        if etut_o is not None and sinif_o is not None:
            fark = etut_o - sinif_o
        if row["zayif"] or (fark is not None and fark <= -5):
            zayif.append(
                {
                    **row,
                    "sinif_ortalama": sinif_o,
                    "fark": fark,
                }
            )
    zayif.sort(key=lambda r: float(r["ortalama"]))
    zayif = zayif[:limit]

    son_iki = list(Deneme.objects.order_by("-tarih", "-id")[:2])
    dusen = []
    if len(son_iki) == 2:
        yeni, eski = son_iki[0], son_iki[1]
        for talebe in etut.talebeler.select_related("sinif"):
            y = deneme_ortalama(yeni, [talebe.id])
            e = deneme_ortalama(eski, [talebe.id])
            if y is None or e is None:
                continue
            if float(y) <= float(e) - 3:
                dusen.append(
                    {
                        "talebe": talebe,
                        "eski": e,
                        "yeni": y,
                        "delta": _avg_or_none(float(y) - float(e)),
                    }
                )
        dusen.sort(key=lambda r: float(r["delta"]))
        dusen = dusen[:limit]

    return {
        "deneme": deneme,
        "zayif_konular": zayif,
        "dusen_talebeler": dusen,
    }


def etut_deneme_siralamasi(etut, deneme: Deneme) -> list[dict]:
    """Deneme genel sıralaması (talebe ortalama yüzde)."""
    talebe_ids = list(etut.talebeler.values_list("id", flat=True))
    rows = (
        KonuSonuc.objects.filter(
            deneme=deneme,
            talebe_id__in=talebe_ids,
            yuzde__isnull=False,
        )
        .values("talebe_id", "talebe__ad_soyad", "talebe__sinif__ad")
        .annotate(
            ortalama=Avg("yuzde"),
            konu_sayisi=Count("konu_id", distinct=True),
        )
        .order_by("-ortalama")
    )
    sonuc = []
    for i, row in enumerate(rows, start=1):
        sonuc.append(
            {
                "sira": i,
                "talebe_id": row["talebe_id"],
                "ad_soyad": row["talebe__ad_soyad"],
                "sinif": row["talebe__sinif__ad"],
                "ortalama": _avg_or_none(row["ortalama"]),
                "konu_sayisi": row["konu_sayisi"],
            }
        )
    return sonuc


def talebe_gelisim_serisi(talebe: Talebe) -> dict:
    """Talebenin deneme deneme genel ortalaması."""
    denemeler = list(Deneme.objects.order_by("tarih", "id"))
    labels = []
    values: list[float | None] = []
    for deneme in denemeler:
        labels.append(deneme.ad)
        avg = deneme_ortalama(deneme, [talebe.id])
        values.append(float(avg) if avg is not None else None)
    return {
        "labels": labels,
        "puanlar": values,
        "trend": _trend(values),
        "son_ortalama": _avg_or_none(values[-1]) if values and values[-1] is not None else None,
    }


def talebe_deneme_kazanimlari(talebe: Talebe, deneme: Deneme) -> list[dict]:
    """Bir denemede talebenin konu sonuçları; zayıflar önde."""
    rows = list(
        KonuSonuc.objects.filter(talebe=talebe, deneme=deneme)
        .select_related("konu", "konu__ders")
        .order_by("konu__ders__ad", "konu__ad")
    )
    sonuc = []
    for row in rows:
        zayif = row.yuzde is not None and row.yuzde < ZAYIF_ESIK
        sonuc.append(
            {
                "konu_id": row.konu_id,
                "ders": row.konu.ders.ad,
                "konu": row.konu.ad,
                "yuzde": row.yuzde,
                "net_dogru": row.net_dogru,
                "net_toplam": row.net_toplam,
                "zayif": zayif,
            }
        )
    sonuc.sort(key=lambda r: (not r["zayif"], float(r["yuzde"] or 999)))
    return sonuc


def talebe_deneme_kutulari(talebe: Talebe) -> list[dict]:
    """Talebe detayında alt deneme kutuları."""
    krono = list(Deneme.objects.order_by("tarih", "id"))
    series = [deneme_ortalama(d, [talebe.id]) for d in krono]
    by_id = {
        d.id: (
            float(series[i]) if series[i] is not None else None,
            float(series[i - 1]) if i and series[i - 1] is not None else None,
        )
        for i, d in enumerate(krono)
    }

    kutular = []
    for deneme in Deneme.objects.order_by("-tarih", "-id"):
        if not KonuSonuc.objects.filter(talebe=talebe, deneme=deneme).exists():
            continue
        kazanimlar = talebe_deneme_kazanimlari(talebe, deneme)
        zayiflar = [k for k in kazanimlar if k["zayif"]]
        cur, prev = by_id.get(deneme.id, (None, None))
        if cur is None or prev is None:
            trend = "→"
        elif cur - prev >= 1.5:
            trend = "↑"
        elif cur - prev <= -1.5:
            trend = "↓"
        else:
            trend = "→"
        kutular.append(
            {
                "deneme": deneme,
                "ortalama": deneme_ortalama(deneme, [talebe.id]),
                "trend": trend,
                "kazanimlar": kazanimlar,
                "zayiflar": zayiflar[:6],
                "zayif_sayisi": len(zayiflar),
                "konu_sayisi": len(kazanimlar),
            }
        )
    return kutular


def etut_talebe_kutulari(etut) -> list[dict]:
    """Etüt talebe galerisi."""
    son_deneme = Deneme.objects.order_by("-tarih", "-id").first()
    kutular = []
    for talebe in etut.talebeler.select_related("sinif").order_by("ad_soyad"):
        gelisim = talebe_gelisim_serisi(talebe)
        son = gelisim["son_ortalama"]
        zayif_sayisi = 0
        if son_deneme:
            zayif_sayisi = sum(
                1
                for k in talebe_deneme_kazanimlari(talebe, son_deneme)
                if k["zayif"]
            )
        kutular.append(
            {
                "talebe": talebe,
                "son_ortalama": son,
                "trend": gelisim["trend"],
                "zayif_sayisi": zayif_sayisi,
                "deneme_sayisi": sum(
                    1 for v in gelisim["puanlar"] if v is not None
                ),
            }
        )
    return kutular
