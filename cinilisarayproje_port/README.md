# Çinili Saray Proje (cinilisarayproje.com) — Etüt Kontrol portu

Canlı site **kitap_takip_premium_v6** reposundan Render’a deploy edilir.
Bu klasör, o repoya uygulanacak Etüt Kontrol + KonuKazanimDetay paketidir.

## Uygula

```bash
git clone https://github.com/yahyayazici/kitap_takip_premium_v6.git
cd kitap_takip_premium_v6
git checkout -b cursor/etut-kontrol-kazanim-3a2b
git apply /path/to/cinilisarayproje_port/etut-kontrol-kazanim.diff
# veya: git am cinilisarayproje_port/patches/*.patch
git push -u origin cursor/etut-kontrol-kazanim-3a2b
# PR aç → main merge → Render otomatik deploy
```

## Canlıda kullanım

1. Yönetim → Denemeler → aktif deneme → **KonuKazanimDetay Excel yükle**
2. Panel menü **Eğitim → Etüt Kontrol**
3. Grafik / dikkat / deneme kutuları / talebe dosyaları / PDF–Excel

Kitap, mevcut deneme Excel ve Gap PDF akışları bozulmaz.
