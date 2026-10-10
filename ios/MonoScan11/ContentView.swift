import SwiftUI
import ARKit

// Screens map directly to docs/ui/MonoScan11-iPhone11-Wireframe-v1.txt.
struct ContentView: View {
    @StateObject private var store = ScanStore()
    @AppStorage("monoscan11.onboardingCompleted") private var onboardingCompleted = false
    @State private var splash = true

    var body: some View {
        Group {
            if splash { SplashScreen() }
            else if !onboardingCompleted {
                OnboardingScreen { onboardingCompleted = true }
            } else {
                MainTabs(store: store)
            }
        }
        .preferredColorScheme(.dark)
        .task {
            try? await Task.sleep(nanoseconds: 900_000_000)
            splash = false
        }
    }
}

// 01 Splash
struct SplashScreen: View {
    var body: some View {
        VStack(spacing: 15) {
            Spacer()
            Image(systemName: "cube.transparent")
                .font(.system(size: 86, weight: .ultraLight)).foregroundStyle(MS.cyan)
                .accessibilityHidden(true)
            Text("MonoScan11").font(.largeTitle.bold()).foregroundStyle(MS.cyan)
            Text("LiDAR olmadan, görüntülerden 3D.").font(.headline).multilineTextAlignment(.center)
            Spacer()
            Text("Araştırma prototipi • v0.2-alpha").font(.caption).foregroundStyle(MS.muted)
        }
        .padding(28).frame(maxWidth: .infinity).msScreen()
    }
}

// 02–04 onboarding
struct OnboardingScreen: View {
    let complete: () -> Void
    @State private var page = 0
    private let pageTitles = ["MonoScan11 Nasıl Çalışır?", "Doğru Çekim Daha İyi Sonuç", "Çıktılar ve Sonraki Adım"]
    private let cards: [[(String, String)]] = [
        [("camera", "Görüntüleri yakala"), ("point.topleft.down.to.point.bottomright.curvepath", "Kamera hareketini kaydet"), ("desktopcomputer", "Windows'ta 3D oluştur")],
        [("figure.walk", "Yavaş hareket et"), ("square.on.square", "Kareler arasında örtüşme bırak"), ("sun.max", "Sabit ışık kullan"), ("exclamationmark.triangle", "Yansımalı yüzeylerden kaçın")],
        [("photo.on.rectangle", "Görüntüler"), ("doc.text", "Oturum metaverisi"), ("shippingbox", "Pozlar (varsa) ve ZIP paketi")]
    ]
    var body: some View {
        VStack(alignment: .leading, spacing: 24) {
            HStack {
                if page > 0 { Button("Geri") { page -= 1 } }
                Spacer()
                Text("\(page + 1)/3").font(.subheadline.monospacedDigit())
                Spacer()
                Button("Atla", action: complete)
            }.foregroundStyle(MS.cyan)
            ProgressView(value: Double(page + 1), total: 3).tint(MS.cyan)
            Spacer(minLength: 8)
            Image(systemName: ["camera.metering.multispot", "viewfinder", "square.stack.3d.up"][page])
                .font(.system(size: 66)).foregroundStyle(MS.cyan).frame(maxWidth: .infinity)
            Text(pageTitles[page]).font(.title.bold())
            ForEach(cards[page].indices, id: \.self) { index in
                MSCard {
                    Label(cards[page][index].1, systemImage: cards[page][index].0).font(.body.weight(.medium)).foregroundStyle(.white)
                }
            }
            Spacer(minLength: 10)
            Notice(text: page == 2 ? "3D model iPhone'da değil, Windows üzerinde oluşturulur." : "MonoScan11 arka LiDAR kullanmaz.")
            MSButton(title: page == 2 ? "Başla" : "İleri", systemImage: "arrow.right") {
                if page < 2 { page += 1 } else { complete() }
            }
        }.padding(20).msScreen()
    }
}

private enum MainTab: Hashable { case home, projects, guide, settings }

struct MainTabs: View {
    @ObservedObject var store: ScanStore
    @State private var selected: MainTab = .home
    @State private var showingFlow = false

    var body: some View {
        TabView(selection: $selected) {
            NavigationStack {
                HomeScreen(store: store, newScan: { showingFlow = true }, goProjects: { selected = .projects }, goGuide: { selected = .guide })
                    .navigationDestination(for: UUID.self) { id in ProjectDetailScreen(store: store, id: id) }
            }.tabItem { Label("Ana Sayfa", systemImage: "house") }.tag(MainTab.home)
            NavigationStack {
                ProjectsScreen(store: store, newScan: { showingFlow = true })
                    .navigationDestination(for: UUID.self) { id in ProjectDetailScreen(store: store, id: id) }
            }.tabItem { Label("Taramalar", systemImage: "viewfinder") }.tag(MainTab.projects)
            NavigationStack { GuideScreen(newScan: { showingFlow = true }) }
                .tabItem { Label("Rehber", systemImage: "book") }.tag(MainTab.guide)
            NavigationStack { SettingsScreen(store: store) }
                .tabItem { Label("Ayarlar", systemImage: "gearshape") }.tag(MainTab.settings)
        }
        .tint(MS.cyan)
        .fullScreenCover(isPresented: $showingFlow) {
            CaptureFlow(store: store, dismiss: { showingFlow = false })
                .preferredColorScheme(.dark)
        }
        .alert("İşlem tamamlanamadı", isPresented: Binding(get: { store.lastError != nil }, set: { if !$0 { store.lastError = nil } })) {
            Button("Tamam") { store.lastError = nil }
        } message: { Text(store.lastError ?? "") }
    }
}

// 05 Dashboard
struct HomeScreen: View {
    @ObservedObject var store: ScanStore
    let newScan: () -> Void
    let goProjects: () -> Void
    let goGuide: () -> Void

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("MonoScan11").font(.largeTitle.bold()).foregroundStyle(MS.cyan)
                        Text("iPhone 11 • Kamera tabanlı tarama").font(.footnote).foregroundStyle(MS.muted)
                    }
                    Spacer()
                    Button(action: goGuide) { Image(systemName: "questionmark.circle").font(.title2) }.accessibilityLabel("Çekim rehberi")
                }
                MSCard {
                    HStack { Text("Yeni Tarama").font(.title2.bold()); Spacer(); Image(systemName: "viewfinder").font(.title).foregroundStyle(MS.cyan) }
                    Text("Bir nesne veya mekân bölümü için görüntü topla.").foregroundStyle(MS.muted)
                    MSButton(title: "Tarama Başlat", systemImage: "arrow.right", action: newScan)
                }
                HStack(spacing: 12) {
                    Button(action: goProjects) {
                        MSCard { Label("Projelerim", systemImage: "folder").foregroundStyle(MS.cyan); Text("Önceki çekimler").font(.caption).foregroundStyle(MS.muted) }
                    }.buttonStyle(.plain)
                    Button(action: goProjects) {
                        MSCard { Label("Dışa Aktarımlar", systemImage: "shippingbox").foregroundStyle(MS.cyan); Text("Veri paketleri").font(.caption).foregroundStyle(MS.muted) }
                    }.buttonStyle(.plain)
                }
                SectionTitle(text: "Son Projeler")
                if store.projects.isEmpty { Notice(text: "Henüz tarama yok. İlk taramanı başlat.", symbol: "folder") }
                else {
                    ForEach(store.projects.prefix(2)) { item in
                        NavigationLink(value: item.id) { ProjectRow(project: item) }.buttonStyle(.plain)
                    }
                }
            }.padding(20)
        }.msScreen().navigationBarHidden(true)
    }
}

struct ProjectRow: View {
    let project: ScanProject
    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: project.target.symbol)
                .font(.title2).foregroundStyle(MS.cyan).frame(width: 52, height: 52)
                .background(MS.panel2, in: RoundedRectangle(cornerRadius: 10))
            VStack(alignment: .leading, spacing: 4) {
                Text(project.name).fontWeight(.semibold).lineLimit(1)
                Text("\(project.imageCount) fotoğraf • \(project.phase.title)")
                    .font(.caption).foregroundStyle(MS.muted)
            }
            Spacer()
            Image(systemName: "chevron.right").foregroundStyle(MS.muted)
        }.padding(12).background(MS.panel, in: RoundedRectangle(cornerRadius: 14))
    }
}
