import SwiftUI

// 16 Guide
struct GuideScreen: View {
    let newScan: () -> Void
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                Text("Çekim Rehberi").font(.largeTitle.bold())
                Image(systemName: "camera.metering.multispot").font(.system(size: 70))
                    .frame(maxWidth: .infinity).foregroundStyle(MS.cyan).padding(24)
                ForEach(["Nesnenin etrafından farklı açılar yakala.",
                         "Fotoğraflar arasında bol örtüşme bırak.",
                         "Kamera hareketini yavaş ve kararlı tut.",
                         "Yansımalı veya dokusuz yüzeylerden kaçın."], id: \.self) { advice in
                    MSCard { Label(advice, systemImage: "checkmark.circle").foregroundStyle(.white) }
                }
                SectionTitle(text: "Sık Sorulan Sorular")
                Group {
                    DisclosureGroup("LiDAR gerekiyor mu?") { Text("Hayır. iPhone 11 RGB kamera ve ARKit pozlarını kullanır.").padding(.top, 8) }
                    DisclosureGroup("Kaç fotoğraf çekmeliyim?") { Text("30–60 farklı açı önerilir. Bu bir başarı garantisi değildir.").padding(.top, 8) }
                    DisclosureGroup("Windows neden gerekiyor?") { Text("Çoklu-görüş rekonstrüksiyonu COLMAP ile Windows'ta gerçekleştirilir.").padding(.top, 8) }
                    DisclosureGroup("Poz kaydı olmasa da çalışır mı?") { Text("Fotoğraflardan SfM uygulanabilir; sonuçlar sahneye bağlıdır.").padding(.top, 8) }
                }.padding(14).background(MS.panel, in: RoundedRectangle(cornerRadius: 12))
                MSButton(title: "Yeni Tarama", systemImage: "plus", action: newScan)
            }.padding(20)
        }.msScreen().navigationBarHidden(true)
    }
}

// 17 Settings (only controls with implemented effects)
struct SettingsScreen: View {
    @ObservedObject var store: ScanStore
    @AppStorage("monoscan11.captureTips") private var captureTips = true
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                Text("Ayarlar").font(.largeTitle.bold())
                SectionTitle(text: "Çekim")
                MSCard {
                    Toggle("Çekim ipuçlarını göster", isOn: $captureTips).tint(MS.cyan)
                    Notice(text: "Varsayılan mod: Kamera + ARKit. Fotoğraf dizisi henüz uygulanmadı.")
                }
                SectionTitle(text: "Depolama")
                MSCard {
                    HStack { Text("Kaydedilen projeler"); Spacer(); Text("\(store.projects.count)") }
                    Text("Projeleri Taramalar bölümünden kalıcı olarak silebilirsin.").font(.footnote).foregroundStyle(MS.muted)
                }
                SectionTitle(text: "Gizlilik")
                MSCard {
                    Text("Görüntüler ve kamera verileri cihazda tutulur. Paylaşım yalnızca sen başlattığında gerçekleşir.")
                }
                SectionTitle(text: "Hakkında")
                MSCard {
                    metric("Uygulama", "MonoScan11")
                    metric("Sürüm", "0.2.0-alpha")
                    Text("LiDAR değil, RGB + ARKit VIO. Tam 3D model Windows'ta oluşturulur.")
                        .font(.footnote).foregroundStyle(MS.muted)
                    Text("MIT lisansı • macOS/Xcode ve gerçek iPhone testleri bekliyor.")
                        .font(.caption).foregroundStyle(MS.muted)
                }
            }.padding(20)
        }.msScreen().navigationBarHidden(true)
    }
}

// 18 Error recovery; structured states, no invented error metrics.
enum RecoveryKind: String, CaseIterable {
    case permission = "Kamera erişimi reddedildi"
    case storage = "Depolama yetersiz"
    case photos = "Çok az fotoğraf"
    case tracking = "ARKit takibi sınırlı"
    case archive = "ZIP oluşturulamadı"
    var detail: String {
        switch self {
        case .permission: return "Ayarlar'dan kamera erişimini etkinleştir."
        case .storage: return "Cihaz depolamasını kontrol et."
        case .photos: return "Nesnenin farklı açılarından daha fazla kare kaydet."
        case .tracking: return "Işığı iyileştir ve telefonu daha yavaş hareket ettir."
        case .archive: return "Boş alanı ve session.json bütünlüğünü kontrol edip tekrar dene."
        }
    }
    var symbol: String { self == .tracking ? "viewfinder" : "exclamationmark.triangle" }
}

struct RecoveryScreen: View {
    let kind: RecoveryKind
    let retry: () -> Void
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text("Sorun ve Çözüm").font(.title2.bold())
            MSCard {
                Label(kind.rawValue, systemImage: kind.symbol).font(.headline).foregroundStyle(.orange)
                Text(kind.detail).foregroundStyle(MS.muted)
            }
            Spacer()
            MSButton(title: "Tekrar Dene", action: retry)
        }.padding(20).msScreen()
    }
}
