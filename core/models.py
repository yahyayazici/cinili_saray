from django.conf import settings
from django.db import models


class Sinif(models.Model):
    ad = models.CharField(max_length=32, unique=True)

    class Meta:
        verbose_name = "Sınıf"
        verbose_name_plural = "Sınıflar"
        ordering = ["ad"]

    def __str__(self):
        return self.ad


class Talebe(models.Model):
    sinif = models.ForeignKey(
        Sinif,
        on_delete=models.CASCADE,
        related_name="talebeler",
    )
    ad_soyad = models.CharField(max_length=160)
    ad_soyad_key = models.CharField(max_length=160, db_index=True)

    class Meta:
        verbose_name = "Talebe"
        verbose_name_plural = "Talebeler"
        ordering = ["ad_soyad"]
        constraints = [
            models.UniqueConstraint(
                fields=["sinif", "ad_soyad_key"],
                name="uniq_talebe_sinif_ad",
            ),
        ]

    def __str__(self):
        return f"{self.ad_soyad} ({self.sinif.ad})"


class Ders(models.Model):
    ad = models.CharField(max_length=160)
    ad_key = models.CharField(max_length=160, unique=True)

    class Meta:
        verbose_name = "Ders"
        verbose_name_plural = "Dersler"
        ordering = ["ad"]

    def __str__(self):
        return self.ad


class Konu(models.Model):
    ders = models.ForeignKey(
        Ders,
        on_delete=models.CASCADE,
        related_name="konular",
    )
    ad = models.CharField(max_length=255)
    ad_key = models.CharField(max_length=255, db_index=True)

    class Meta:
        verbose_name = "Konu"
        verbose_name_plural = "Konular"
        ordering = ["ders__ad", "ad"]
        constraints = [
            models.UniqueConstraint(
                fields=["ders", "ad_key"],
                name="uniq_konu_ders_ad",
            ),
        ]

    def __str__(self):
        return f"{self.ders.ad} · {self.ad}"


class Deneme(models.Model):
    ad = models.CharField(max_length=160)
    tarih = models.DateField()
    kaynak_dosya = models.CharField(max_length=255, blank=True)
    olusturulma = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Deneme"
        verbose_name_plural = "Denemeler"
        ordering = ["-tarih", "-olusturulma"]

    def __str__(self):
        return f"{self.ad} ({self.tarih})"


class KonuSonuc(models.Model):
    deneme = models.ForeignKey(
        Deneme,
        on_delete=models.CASCADE,
        related_name="sonuclar",
    )
    talebe = models.ForeignKey(
        Talebe,
        on_delete=models.CASCADE,
        related_name="sonuclar",
    )
    konu = models.ForeignKey(
        Konu,
        on_delete=models.CASCADE,
        related_name="sonuclar",
    )
    yuzde = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
    )
    net_dogru = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )
    net_toplam = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Konu sonucu"
        verbose_name_plural = "Konu sonuçları"
        constraints = [
            models.UniqueConstraint(
                fields=["deneme", "talebe", "konu"],
                name="uniq_sonuc_deneme_talebe_konu",
            ),
        ]

    def __str__(self):
        return f"{self.talebe} · {self.konu} · {self.deneme}"


class Etut(models.Model):
    """Etüt grubu — hocanın takip ettiği talebe kümesi."""

    ad = models.CharField(max_length=160)
    hoca = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="etutler",
        null=True,
        blank=True,
    )
    talebeler = models.ManyToManyField(
        Talebe,
        related_name="etutler",
        blank=True,
    )
    aktif = models.BooleanField(default=True)
    olusturulma = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Etüt"
        verbose_name_plural = "Etütler"
        ordering = ["ad"]

    def __str__(self):
        return self.ad
