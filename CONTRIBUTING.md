# Katkı kuralları

1. `python -m unittest discover -s tests -v` çalıştırın.
2. Yeni algoritma eklerken sentetik test ve bozuk-girdi/başarısızlık testi ekleyin.
3. Donanım, gerçek veri veya CUDA üzerinde test yapmadıysanız sonuçları *PASS* olarak işaretlemeyin.
4. iPhone 11 kamera ve poz verilerini GitHub'a yüklemeyin; örnek ihtiyaçları için deterministik sentetik veri üretin.
5. macOS/Xcode işlerini `docs/SON_ASAMAYA_BIRAKILANLAR.md` kapsamından ancak gerçek kabul kanıtlarıyla çıkarın.

Öncelik: Doğru I/O ve kaynak verisi > baseline > test > benchmark > optimizasyon > rapor.
