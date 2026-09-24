from datetime import date
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from core.etut_stats import etut_konu_ozeti, etut_konu_talebe_satirlari, sinif_raporu
from core.kazanim_import import import_kazanim_excel
from core.models import Deneme, Ders, Etut, Konu, KonuSonuc, Talebe

SAMPLE = Path(
    "/home/ubuntu/.cursor/projects/workspace/uploads/"
    "KonuKazanimDetay_23.09.2026_8c21.xlsx"
)


class KazanimImportTests(TestCase):
    def test_import_creates_topics_and_reuses_on_second_upload(self):
        self.assertTrue(SAMPLE.exists(), "Örnek Excel bulunamadı")

        with SAMPLE.open("rb") as fh:
            first = import_kazanim_excel(
                fh,
                deneme_adi="1. Deneme",
                deneme_tarihi=date(2026, 9, 23),
            )

        self.assertGreater(first.sonuc_yazilan, 0)
        self.assertGreater(first.konu_yeni, 0)
        konu_count = Konu.objects.count()
        ders_count = Ders.objects.count()
        talebe_count = Talebe.objects.count()

        with SAMPLE.open("rb") as fh:
            second = import_kazanim_excel(
                fh,
                deneme_adi="2. Deneme",
                deneme_tarihi=date(2026, 9, 30),
            )

        self.assertEqual(second.konu_yeni, 0)
        self.assertEqual(second.konu_mevcut, konu_count)
        self.assertEqual(second.ders_yeni, 0)
        self.assertEqual(Konu.objects.count(), konu_count)
        self.assertEqual(Ders.objects.count(), ders_count)
        self.assertEqual(Talebe.objects.count(), talebe_count)
        self.assertEqual(Deneme.objects.count(), 2)
        self.assertEqual(
            KonuSonuc.objects.filter(deneme_id=second.deneme_id).count(),
            second.sonuc_yazilan,
        )

    def test_upload_view_requires_login_and_imports(self):
        user = get_user_model().objects.create_user("admin", password="admin123")
        client = Client()
        client.login(username="admin", password="admin123")

        with SAMPLE.open("rb") as fh:
            response = client.post(
                "/panel/akademik/yukle/",
                {
                    "deneme_adi": "KTT-1",
                    "deneme_tarihi": "2026-09-23",
                    "rapor": fh,
                },
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Deneme.objects.count(), 1)
        deneme = Deneme.objects.get()
        self.assertEqual(deneme.ad, "KTT-1")


class EtutPanelTests(TestCase):
    def setUp(self):
        with SAMPLE.open("rb") as fh:
            stats = import_kazanim_excel(
                fh,
                deneme_adi="Etüt Deneme",
                deneme_tarihi=date(2026, 9, 23),
            )
        self.deneme = Deneme.objects.get(pk=stats.deneme_id)
        self.user = get_user_model().objects.create_user("hoca", password="hoca123")
        self.etut = Etut.objects.create(ad="Test Etüt", hoca=self.user)
        self.etut.talebeler.set(Talebe.objects.all()[:5])
        self.konu = Konu.objects.filter(ad__icontains="SÖZCÜKTE").first()
        self.assertIsNotNone(self.konu)

    def test_etut_average_and_class_report(self):
        ozet = etut_konu_ozeti(self.etut, deneme=self.deneme)
        self.assertTrue(any(r["konu_id"] == self.konu.id for r in ozet))
        satirlar, ortalama = etut_konu_talebe_satirlari(
            self.etut, self.konu, self.deneme
        )
        self.assertEqual(len(satirlar), 5)
        self.assertIsNotNone(ortalama)
        rapor = sinif_raporu(self.deneme)
        self.assertTrue(any(r["konu_id"] == self.konu.id for r in rapor))

    def test_etut_konu_page(self):
        client = Client()
        client.login(username="hoca", password="hoca123")
        url = (
            f"/panel/etut/{self.etut.id}/konu/{self.konu.id}/"
            f"?deneme={self.deneme.id}"
        )
        resp = client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Etüt ortalaması")
        self.assertContains(resp, "Sınıf ortalaması")
        self.assertContains(resp, "SÖZCÜKTE ANLAM")
