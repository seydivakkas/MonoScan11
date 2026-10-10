# Güvenlik

Bu yazılım yerel ortam görüntülerini işleyen deneysel bir araştırma prototipidir. Gizli ev/işyeri fotoğraflarını, `session.json`, kamera pozlarını ve ham rekonstrüksiyon çıktılarını herkese açık issue/PR/repo içeriklerine eklemeyin.

- Ağ erişimi gerektiren bir backend bulunmaz. COLMAP isteğe bağlı ayrı kurulur.
- Mevcut `reconstruction` çıktıları varsayılan olarak üzerine yazılmaz.
- `session.json` dosya adlarının yol dışına çıkması, bozuk JPEG/PNG başlığı, sayısal taşma / sonlu olmayan değerler gibi girdiler kontrol edilir. Bu kontroller *tam bir görüntü dekoder güvenlik denetimi değildir*.
- COLMAP'i yalnızca doğruladığınız resmi dağıtımlardan edinin. iOS uygulaması henüz cihazda test edilmemiştir.

Bulgular için herkese açık issue'da özel veri paylaşmadan, tekrar üretim adımlarını ve güvenli sentetik örneği açıklayın.
