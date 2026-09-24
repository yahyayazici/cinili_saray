from datetime import datetime
import json

from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render

from core.kazanim_import import import_kazanim_excel
from core.exports import (
    excel_kazanim,
    excel_sinif_raporu,
    excel_siralama,
    excel_talebe_kazanim,
    pdf_kazanim,
    pdf_sinif_raporu,
    pdf_siralama,
    pdf_talebe_kazanim,
)
from core.etut_stats import (
    etut_baskin_sinif,
    etut_deneme_kutulari,
    etut_deneme_siralamasi,
    etut_dikkat,
    etut_gelisim_serisi,
    etut_konu_ozeti,
    etut_konu_talebe_satirlari,
    etut_talebe_kutulari,
    sinif_konu_karsilastirma,
    sinif_raporu,
    talebe_deneme_kutulari,
    talebe_gelisim_serisi,
)
from core.models import Deneme, Ders, Etut, Konu, KonuSonuc, Sinif, Talebe


def home(request):
    return render(request, "home.html")


def login_view(request):
    error_message = None

    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        user = authenticate(
            request,
            username=username,
            password=password,
        )

        if user is not None:
            auth_login(request, user)
            return redirect("dashboard")

        error_message = "Kullanıcı adı veya şifre hatalı."

    return render(
        request,
        "login.html",
        {"error_message": error_message},
    )


@login_required(login_url="login")
def dashboard(request):
    return render(
        request,
        "dashboard.html",
        {
            "deneme_sayisi": Deneme.objects.count(),
            "talebe_sayisi": Talebe.objects.count(),
            "konu_sayisi": Konu.objects.count(),
        },
    )


@login_required(login_url="login")
def akademik_takip(request):
    denemeler = Deneme.objects.annotate(
        sonuc_sayisi=Count("sonuclar"),
    )
    return render(
        request,
        "akademik_takip.html",
        {
            "denemeler": denemeler,
            "ders_sayisi": Ders.objects.count(),
            "konu_sayisi": Konu.objects.count(),
            "talebe_sayisi": Talebe.objects.count(),
        },
    )


@login_required(login_url="login")
def deneme_yukle(request):
    if request.method == "POST":
        deneme_adi = request.POST.get("deneme_adi", "").strip()
        tarih_raw = request.POST.get("deneme_tarihi", "").strip()
        dosya = request.FILES.get("rapor")

        if not deneme_adi or not tarih_raw or not dosya:
            messages.error(request, "Deneme adı, tarih ve Excel dosyası zorunlu.")
            return redirect("deneme_yukle")

        try:
            deneme_tarihi = datetime.strptime(tarih_raw, "%Y-%m-%d").date()
        except ValueError:
            messages.error(request, "Tarih formatı geçersiz.")
            return redirect("deneme_yukle")

        if not dosya.name.lower().endswith((".xlsx", ".xlsm")):
            messages.error(request, "Lütfen .xlsx formatında bir dosya yükleyin.")
            return redirect("deneme_yukle")

        try:
            stats = import_kazanim_excel(
                dosya,
                deneme_adi=deneme_adi,
                deneme_tarihi=deneme_tarihi,
            )
        except Exception as exc:
            messages.error(request, f"İçe aktarma başarısız: {exc}")
            return redirect("deneme_yukle")

        messages.success(
            request,
            (
                f"“{deneme_adi}” yüklendi. "
                f"{stats.sonuc_yazilan} sonuç kaydı · "
                f"yeni konu {stats.konu_yeni}, mevcut konu {stats.konu_mevcut} · "
                f"yeni ders {stats.ders_yeni}, mevcut ders {stats.ders_mevcut} · "
                f"yeni talebe {stats.talebe_yeni}."
            ),
        )
        for uyari in stats.uyari:
            messages.warning(request, uyari)

        return redirect("deneme_detay", deneme_id=stats.deneme_id)

    return render(request, "deneme_yukle.html")


@login_required(login_url="login")
def deneme_detay(request, deneme_id):
    deneme = get_object_or_404(Deneme, pk=deneme_id)
    sonuclar = (
        KonuSonuc.objects.filter(deneme=deneme)
        .select_related("talebe", "talebe__sinif", "konu", "konu__ders")
        .order_by("talebe__ad_soyad", "konu__ders__ad", "konu__ad")
    )

    # Talebe × konu özeti için gruplu görünüm
    talebe_map = {}
    for sonuc in sonuclar:
        bucket = talebe_map.setdefault(
            sonuc.talebe_id,
            {"talebe": sonuc.talebe, "satirlar": []},
        )
        bucket["satirlar"].append(sonuc)

    return render(
        request,
        "deneme_detay.html",
        {
            "deneme": deneme,
            "talebe_gruplari": list(talebe_map.values()),
            "sonuc_sayisi": sonuclar.count(),
            "konu_sayisi": (
                KonuSonuc.objects.filter(deneme=deneme)
                .values("konu")
                .distinct()
                .count()
            ),
        },
    )


@login_required(login_url="login")
def konu_listesi(request):
    konular = Konu.objects.select_related("ders").annotate(
        sonuc_sayisi=Count("sonuclar"),
    )
    return render(
        request,
        "konu_listesi.html",
        {"konular": konular},
    )


def _hoca_etutleri(user):
    qs = Etut.objects.filter(aktif=True).prefetch_related("talebeler", "talebeler__sinif")
    if user.is_superuser:
        return qs
    own = qs.filter(hoca=user)
    if own.exists():
        return own
    # Henüz atanmamışsa tüm aktif etütleri göster (demo / tek kullanıcı)
    return qs


@login_required(login_url="login")
def etut_panel(request):
    """Eski giriş → Etüt Kontrol'e yönlendir."""
    etutler = _hoca_etutleri(request.user)
    etut = etutler.first()
    if etut is None:
        return render(
            request,
            "etut_kontrol.html",
            {"etut": None, "etutler": etutler},
        )
    etut_id = request.GET.get("etut")
    if etut_id:
        return redirect("etut_kontrol", etut_id=etut_id)
    return redirect("etut_kontrol", etut_id=etut.id)


@login_required(login_url="login")
def etut_kontrol(request, etut_id):
    """Etüt hocasının ana üssü: grafik + dikkat + deneme kutuları."""
    etut = get_object_or_404(
        Etut.objects.prefetch_related("talebeler", "talebeler__sinif"),
        pk=etut_id,
    )
    etutler = _hoca_etutleri(request.user)
    gelisim = etut_gelisim_serisi(etut)
    dikkat = etut_dikkat(etut)
    kutular = etut_deneme_kutulari(etut)
    return render(
        request,
        "etut_kontrol.html",
        {
            "etut": etut,
            "etutler": etutler,
            "gelisim": gelisim,
            "dikkat": dikkat,
            "kutular": kutular,
            "talebe_sayisi": etut.talebeler.count(),
            "gelisim_json": json.dumps(
                {
                    "labels": gelisim["labels"],
                    "etut": gelisim["etut"],
                    "sinif": gelisim["sinif"],
                    "sinif_ad": gelisim["sinif_ad"],
                },
                ensure_ascii=False,
            ),
        },
    )


@login_required(login_url="login")
def etut_deneme_detay(request, etut_id, deneme_id):
    """Deneme kutusu içi: sıralama + kazanım listesi."""
    etut = get_object_or_404(Etut, pk=etut_id)
    deneme = get_object_or_404(Deneme, pk=deneme_id)
    sekme = request.GET.get("sekme", "siralama")
    if sekme not in {"siralama", "kazanim"}:
        sekme = "siralama"

    siralama = etut_deneme_siralamasi(etut, deneme)
    kazanimlar = etut_konu_ozeti(etut, deneme=deneme)
    sinif = etut_baskin_sinif(etut)

    indir = request.GET.get("indir")
    if indir == "excel":
        if sekme == "kazanim":
            return excel_kazanim(etut, deneme, kazanimlar)
        return excel_siralama(etut, deneme, siralama)
    if indir == "pdf":
        if sekme == "kazanim":
            return pdf_kazanim(etut, deneme, kazanimlar)
        return pdf_siralama(etut, deneme, siralama)

    return render(
        request,
        "etut_deneme_detay.html",
        {
            "etut": etut,
            "deneme": deneme,
            "sekme": sekme,
            "siralama": siralama,
            "kazanimlar": kazanimlar,
            "sinif": sinif,
            "etut_ortalama": deneme_ortalama_safe(etut, deneme),
            "sinif_ortalama": (
                deneme_ortalama_safe(etut, deneme, sinif=sinif) if sinif else None
            ),
        },
    )


def deneme_ortalama_safe(etut, deneme, sinif=None):
    from core.etut_stats import deneme_ortalama

    if sinif is not None:
        ids = list(
            Talebe.objects.filter(sinif=sinif).values_list("id", flat=True)
        )
    else:
        ids = list(etut.talebeler.values_list("id", flat=True))
    return deneme_ortalama(deneme, ids)


@login_required(login_url="login")
def etut_detay(request, etut_id):
    return redirect("etut_kontrol", etut_id=etut_id)


@login_required(login_url="login")
def etut_talebeler(request, etut_id):
    """Etüt talebe kutuları."""
    etut = get_object_or_404(Etut, pk=etut_id)
    kutular = etut_talebe_kutulari(etut)
    return render(
        request,
        "etut_talebeler.html",
        {
            "etut": etut,
            "kutular": kutular,
        },
    )


@login_required(login_url="login")
def etut_talebe_detay(request, etut_id, talebe_id):
    """Talebe dosyası: puan grafiği + deneme kazanım kutuları."""
    etut = get_object_or_404(Etut, pk=etut_id)
    talebe = get_object_or_404(Talebe.objects.select_related("sinif"), pk=talebe_id)
    if not etut.talebeler.filter(pk=talebe.id).exists():
        messages.error(request, "Bu talebe seçili etütte değil.")
        return redirect("etut_talebeler", etut_id=etut.id)

    gelisim = talebe_gelisim_serisi(talebe)
    kutular = talebe_deneme_kutulari(talebe)

    indir = request.GET.get("indir")
    if indir == "pdf":
        return pdf_talebe_kazanim(etut, talebe, kutular)
    if indir == "excel":
        return excel_talebe_kazanim(talebe, kutular)

    return render(
        request,
        "etut_talebe_detay.html",
        {
            "etut": etut,
            "talebe": talebe,
            "gelisim": gelisim,
            "kutular": kutular,
            "gelisim_json": json.dumps(
                {
                    "labels": gelisim["labels"],
                    "puanlar": gelisim["puanlar"],
                },
                ensure_ascii=False,
            ),
        },
    )


@login_required(login_url="login")
def etut_konu_detay(request, etut_id, konu_id):
    etut = get_object_or_404(Etut, pk=etut_id)
    konu = get_object_or_404(Konu.objects.select_related("ders"), pk=konu_id)
    denemeler = Deneme.objects.order_by("-tarih")
    deneme_id = request.GET.get("deneme")
    if deneme_id:
        deneme = get_object_or_404(Deneme, pk=deneme_id)
    else:
        deneme = denemeler.first()
        if deneme is None:
            messages.warning(request, "Henüz deneme yüklenmemiş.")
            return redirect("etut_detay", etut_id=etut.id)

    satirlar, etut_ortalama = etut_konu_talebe_satirlari(etut, konu, deneme)

    # Etütteki baskın sınıf
    sinif = (
        etut.talebeler.values_list("sinif", flat=True)
        .order_by()
        .first()
    )
    sinif_obj = Sinif.objects.filter(pk=sinif).first() if sinif else None
    karsilastirma = sinif_konu_karsilastirma(
        deneme, konu, etut, sinif=sinif_obj
    )

    return render(
        request,
        "etut_konu_detay.html",
        {
            "etut": etut,
            "konu": konu,
            "deneme": deneme,
            "denemeler": denemeler,
            "satirlar": satirlar,
            "etut_ortalama": etut_ortalama,
            "sinif": sinif_obj,
            "sinif_ortalama": karsilastirma["sinif_ortalama"],
        },
    )


@login_required(login_url="login")
def deneme_sinif_raporu(request, deneme_id):
    deneme = get_object_or_404(Deneme, pk=deneme_id)
    siniflar = Sinif.objects.filter(
        talebeler__sonuclar__deneme=deneme
    ).distinct()
    sinif_id = request.GET.get("sinif")
    sinif = None
    if sinif_id:
        sinif = get_object_or_404(Sinif, pk=sinif_id)
    elif siniflar.count() == 1:
        sinif = siniflar.first()

    rapor = sinif_raporu(deneme, sinif=sinif)

    indir = request.GET.get("indir")
    if indir == "excel":
        return excel_sinif_raporu(deneme, sinif, rapor)
    if indir == "pdf":
        return pdf_sinif_raporu(deneme, sinif, rapor)

    return render(
        request,
        "deneme_sinif_raporu.html",
        {
            "deneme": deneme,
            "siniflar": siniflar,
            "secili_sinif": sinif,
            "rapor": rapor,
        },
    )
