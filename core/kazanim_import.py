"""Konu kazanım Excel raporunu içe aktarma.

Deneme kutuğu çıktısı (KonuKazanimDetay_*.xlsx):
  satır 1 → ders adları (birleşik hücreler / forward-fill)
  satır 2 → konu / kazanım adları
  satır 3 → metrik: Yüzde | Net
  satır 4+ → Sınıf | Ad Soyad | değerler

Aynı ders/konu adı gelirse mevcut kayıt kullanılır; yeni ad otomatik eklenir.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import transaction
from openpyxl import load_workbook

from core.models import Deneme, Ders, Konu, KonuSonuc, Sinif, Talebe


def clean_label(value) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def name_key(value: str) -> str:
    """Eşleştirme anahtarı: boşluk normalize + Türkçe büyük harf."""
    return clean_label(value).casefold()


def parse_decimal(value) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    text = str(value).strip().replace("%", "").replace(",", ".")
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def parse_net(value) -> tuple[Decimal | None, Decimal | None]:
    """'6,67/8' → (6.67, 8). Boşsa (None, None)."""
    if value is None or value == "":
        return None, None
    text = str(value).strip()
    if not text:
        return None, None
    match = re.match(
        r"^\s*(-?\d+(?:[.,]\d+)?)\s*/\s*(-?\d+(?:[.,]\d+)?)\s*$",
        text,
    )
    if not match:
        return None, None
    return parse_decimal(match.group(1)), parse_decimal(match.group(2))


@dataclass
class ImportStats:
    deneme_id: int | None = None
    talebe_yeni: int = 0
    talebe_mevcut: int = 0
    ders_yeni: int = 0
    ders_mevcut: int = 0
    konu_yeni: int = 0
    konu_mevcut: int = 0
    sonuc_yazilan: int = 0
    atlanan_bos: int = 0
    uyari: list[str] = field(default_factory=list)


def _forward_fill(values: list) -> list[str | None]:
    filled: list[str | None] = []
    current: str | None = None
    for value in values:
        label = clean_label(value)
        if label:
            current = label
        filled.append(current)
    return filled


def _read_columns(ws) -> list[dict]:
    """Kolon 3+ için ders/konu/metrik eşlemesi üretir."""
    row1 = [cell.value for cell in ws[1]]
    row2 = [cell.value for cell in ws[2]]
    row3 = [cell.value for cell in ws[3]]

    subjects = _forward_fill(row1)
    topics = _forward_fill(row2)

    columns: list[dict] = []
    for index in range(2, len(row3)):
        metric_raw = clean_label(row3[index]).casefold()
        if metric_raw not in {"yüzde", "yuzde", "net"}:
            continue
        subject = subjects[index]
        topic = topics[index]
        if not subject or not topic:
            continue
        columns.append(
            {
                "col": index + 1,  # openpyxl 1-based
                "ders": subject,
                "konu": topic,
                "metrik": "yuzde" if "yuzde" in metric_raw or "yüzde" in metric_raw else "net",
            }
        )
    return columns


@transaction.atomic
def import_kazanim_excel(
    uploaded_file,
    *,
    deneme_adi: str,
    deneme_tarihi: date,
) -> ImportStats:
    stats = ImportStats()
    deneme_adi = clean_label(deneme_adi)
    if not deneme_adi:
        raise ValueError("Deneme adı zorunlu.")

    wb = load_workbook(uploaded_file, data_only=True, read_only=False)
    try:
        ws = wb[wb.sheetnames[0]]
        columns = _read_columns(ws)
        if not columns:
            raise ValueError(
                "Excel'de konu kolonları bulunamadı. "
                "KonuKazanimDetay formatında (ders / konu / Yüzde-Net) olmalı."
            )

        # Konu bazında yüzde + net kolonlarını birleştir
        topic_cols: dict[tuple[str, str], dict] = {}
        for col in columns:
            key = (name_key(col["ders"]), name_key(col["konu"]))
            bucket = topic_cols.setdefault(
                key,
                {"ders": col["ders"], "konu": col["konu"], "yuzde_col": None, "net_col": None},
            )
            if col["metrik"] == "yuzde":
                bucket["yuzde_col"] = col["col"]
            else:
                bucket["net_col"] = col["col"]

        ders_cache: dict[str, Ders] = {}
        konu_cache: dict[tuple[int, str], Konu] = {}

        for meta in topic_cols.values():
            dkey = name_key(meta["ders"])
            ders = ders_cache.get(dkey)
            if ders is None:
                ders, created = Ders.objects.get_or_create(
                    ad_key=dkey,
                    defaults={"ad": meta["ders"]},
                )
                ders_cache[dkey] = ders
                if created:
                    stats.ders_yeni += 1
                else:
                    stats.ders_mevcut += 1

            kkey = name_key(meta["konu"])
            cache_key = (ders.id, kkey)
            konu = konu_cache.get(cache_key)
            if konu is None:
                konu, created = Konu.objects.get_or_create(
                    ders=ders,
                    ad_key=kkey,
                    defaults={"ad": meta["konu"]},
                )
                konu_cache[cache_key] = konu
                if created:
                    stats.konu_yeni += 1
                else:
                    stats.konu_mevcut += 1
            meta["konu_obj"] = konu_cache[cache_key]

        kaynak = getattr(uploaded_file, "name", "") or ""
        deneme = Deneme.objects.create(
            ad=deneme_adi,
            tarih=deneme_tarihi,
            kaynak_dosya=kaynak[:255],
        )
        stats.deneme_id = deneme.id

        sinif_cache: dict[str, Sinif] = {}
        talebe_cache: dict[tuple[int, str], Talebe] = {}
        rows_iter = ws.iter_rows(min_row=4, values_only=False)

        for row in rows_iter:
            if not row:
                continue
            sinif_ad = clean_label(row[0].value if len(row) > 0 else None)
            ad_soyad = clean_label(row[1].value if len(row) > 1 else None)
            if not sinif_ad or not ad_soyad:
                continue

            sinif = sinif_cache.get(sinif_ad)
            if sinif is None:
                sinif, _ = Sinif.objects.get_or_create(ad=sinif_ad)
                sinif_cache[sinif_ad] = sinif

            tkey = name_key(ad_soyad)
            tcache_key = (sinif.id, tkey)
            talebe = talebe_cache.get(tcache_key)
            if talebe is None:
                talebe, created = Talebe.objects.get_or_create(
                    sinif=sinif,
                    ad_soyad_key=tkey,
                    defaults={"ad_soyad": ad_soyad},
                )
                talebe_cache[tcache_key] = talebe
                if created:
                    stats.talebe_yeni += 1
                else:
                    stats.talebe_mevcut += 1

            for meta in topic_cols.values():
                yuzde = None
                net_dogru = None
                net_toplam = None

                if meta["yuzde_col"]:
                    idx = meta["yuzde_col"] - 1
                    if idx < len(row):
                        yuzde = parse_decimal(row[idx].value)

                if meta["net_col"]:
                    idx = meta["net_col"] - 1
                    if idx < len(row):
                        net_dogru, net_toplam = parse_net(row[idx].value)

                if yuzde is None and net_dogru is None and net_toplam is None:
                    stats.atlanan_bos += 1
                    continue

                KonuSonuc.objects.update_or_create(
                    deneme=deneme,
                    talebe=talebe,
                    konu=meta["konu_obj"],
                    defaults={
                        "yuzde": yuzde,
                        "net_dogru": net_dogru,
                        "net_toplam": net_toplam,
                    },
                )
                stats.sonuc_yazilan += 1
    finally:
        wb.close()

    if stats.sonuc_yazilan == 0:
        stats.uyari.append("Hiç sonuç satırı yazılmadı; dosyayı kontrol edin.")

    return stats
