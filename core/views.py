from datetime import datetime

from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render

from core.kazanim_import import import_kazanim_excel
from core.etut_stats import (
    etut_konu_ozeti,
    etut_konu_talebe_satirlari,
    sinif_konu_karsilastirma,
    sinif_raporu,
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
    etutler = _hoca_etutleri(request.user).annotate(
        talebe_sayisi=Count("talebeler", distinct=True),
    )
    talebe_ids = (
        Talebe.objects.filter(etutler__in=etutler)
        .values_list("id", flat=True)
        .distinct()
    )
    talebeler = (
        Talebe.objects.filter(id__in=talebe_ids)
        .select_related("sinif")
        .order_by("sinif__ad", "ad_soyad")
    )
    return render(
        request,
        "etut_panel.html",
        {
            "etutler": etutler,
            "talebeler": talebeler,
            "konu_sayisi": Konu.objects.count(),
            "deneme_sayisi": Deneme.objects.count(),
        },
    )


@login_required(login_url="login")
def etut_detay(request, etut_id):
    etut = get_object_or_404(Etut.objects.prefetch_related("talebeler"), pk=etut_id)
    denemeler = Deneme.objects.order_by("-tarih")
    deneme_id = request.GET.get("deneme")
    deneme = None
    if deneme_id:
        deneme = get_object_or_404(Deneme, pk=deneme_id)
    elif denemeler.exists():
        deneme = denemeler.first()

    ozet = etut_konu_ozeti(etut, deneme=deneme)
    return render(
        request,
        "etut_detay.html",
        {
            "etut": etut,
            "talebeler": etut.talebeler.select_related("sinif"),
            "denemeler": denemeler,
            "secili_deneme": deneme,
            "konu_ozeti": ozet,
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
