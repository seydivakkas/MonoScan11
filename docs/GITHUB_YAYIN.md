# MonoScan11 — Windows'tan GitHub'a ilk push

## A. Önce yerel test

`Run-Tests.cmd` dosyasını çalıştırın veya PowerShell'de:

```powershell
python -m unittest discover -s tests -v
python -m compileall -q tools tests
```

`demo-output/` gibi üretilmiş dosyalar ve gerçek fotoğraf klasörleri repoya eklenmemelidir. `git status` ve `git diff --cached --stat` ile denetle.

## B. GitHub CLI ile önerilen tek seferlik yöntem

[Git for Windows](https://git-scm.com/download/win) ve [GitHub CLI](https://cli.github.com/) kurulu olmalıdır. ZIP açtığınız proje klasöründe PowerShell açın:

```powershell
git init -b main
git add .
git status
git commit -m "feat: MonoScan11 offline-first P0 alpha baseline"
gh auth login
gh repo create MonoScan11 --public --source . --remote origin --push
```

**Dikkat:** Son komut yeni bir depo oluşturur; aynı isimde önceden repo varsa oluşturma işlemine girişmeyin. Var olan bir repoya bağlamak için önce `git remote -v` ve GitHub'daki repo adresini denetleyin.

## C. GitHub web sitesinde manuel yöntem

1. Yeni, **boş** `MonoScan11` deposu oluşturun (README/LICENSE/gitignore eklemeyin; burada zaten var).
2. Yukarıdaki ilk dört `git` komutunu çalıştırın.
3. GitHub'ın gösterdiği *gerçek yeni repo URL'sini* kullanın:

```powershell
git remote add origin https://github.com/KULLANICI_ADINIZ/MonoScan11.git
git push -u origin main
```

`KULLANICI_ADINIZ` yer tutucudur; hesabınıza göre değiştirilmelidir.

## D. Push sonrası kontrol

- **Actions > Python tests**: Windows ve Ubuntu işlerinin tamamını PASS olarak doğrula (gerekmedikçe önceki yerel PASS'ı CI PASS yerine kullanma).
- **Code**: iOS dosyalarının prototip olduğunu README'de görünür bul.
- **Security**: Ev/oda fotoğrafları, kişisel dizinler, API anahtarları, sertifikalar bulunmasın.
- **Issues**: `IOS-01` ve `REAL-01` şablonlarıyla eksikleri takip et.
- **Releases**: İlk kaynak kod sürümü gerekirse `v0.1.0-alpha` **pre-release** olarak oluştur. Stable işaretleme.

## E. Sonraki push'larda

```powershell
git status
git add .
git commit -m "test: strengthen offline reconstruction checks"
git push
```

**Mac/Xcode gerektiren aşamaları şimdi yapmayacağız.** Ayrıntılar: [`SON_ASAMAYA_BIRAKILANLAR.md`](SON_ASAMAYA_BIRAKILANLAR.md).

## F. UI-P1 — 18 ekran tasarım paketinin yayını

Bu paket ayrıca şunları içerir:

```text
docs/ui/MonoScan11-iPhone11-Wireframe-v1.txt  # Onaylı Türkçe wireframe şartnamesi
docs/ui/README.md                             # Bütün ekranları gösteren galeri
docs/ui/screens.json                          # 18 ekran manifesti
assets/screenshots/01-...png ... 18-...png    # 18 ayrı 828×1792 PNG
assets/screenshots/contact-sheet.png           # Toplu önizleme
scripts/generate_ui_mockups.py                 # Pillow ile yeniden üretilebilir tasarım kodu
tests/test_ui_assets.py                       # PNG ve manifest regresyon testleri
```

`README.md` içinde arayüz konseptleri bölümü vardır. **Bu PNG'ler gerçek iPhone ekran görüntüsü veya çalışan SwiftUI kodu kanıtı değildir.** iOS/Xcode işlemleri yine son aşamada tutulur.

UI maketlerini yeniden üretmek istersen:

```powershell
python -m pip install "Pillow>=10,<13"
python scripts/generate_ui_mockups.py
python -m unittest discover -s tests -v
```

Kod derlemesi ve testleri yalnız temel Python standart kütüphanesini kullanır; PNG görsel yeniden üretimi için Pillow ayrı ve isteğe bağlı bağımlılıktır.
