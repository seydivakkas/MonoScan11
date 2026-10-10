import SwiftUI
import AVFoundation
import ARKit
import SceneKit

private enum FlowStep { case setup, permissions, capture, review, summary }

// Full-screen flow: 06 Setup -> 07 Permissions -> 08 Capture <-> 09 Review -> 10 Summary.
struct CaptureFlow: View {
    @ObservedObject var store: ScanStore
    let dismiss: () -> Void
    @StateObject private var engine = ScanEngine()
    @State private var step: FlowStep = .setup
    @State private var project: ScanProject?
    @State private var error: String?
    @State private var showExitConfirm = false
    @State private var stopping = false

    var body: some View {
        NavigationStack {
            Group {
                switch step {
                case .setup:
                    NewScanScreen { name, target in
                        do { project = try store.create(name: name, target: target); step = .permissions }
                        catch { self.error = error.localizedDescription }
                    } cancel: { dismiss() }
                case .permissions:
                    PermissionsScreen(back: {
                        if let project { try? store.delete(project.id) }
                        project = nil
                        step = .setup
                    }, start: { step = .capture })
                case .capture, .review:
                    if let project {
                        ZStack {
                            CaptureScreen(engine: engine, folder: store.folder(for: project.id),
                                          name: project.name, close: { showExitConfirm = true },
                                          review: { step = .review })
                            if step == .review {
                                QualityScreen(engine: engine, back: { step = .capture }, finish: finish)
                                    .background(MS.background.ignoresSafeArea())
                            }
                        }
                    }
                case .summary:
                    if let project { SummaryScreen(store: store, id: project.id, finish: dismiss) }
                }
            }
            .navigationBarBackButtonHidden(true)
            .navigationDestination(for: ProjectRoute.self) { route in
                switch route {
                case .gallery(let id): GalleryScreen(store: store, id: id)
                case .preview(let id): SparseScreen(store: store, id: id)
                case .export(let id): ExportScreen(store: store, id: id)
                }
            }
        }
        .alert("Tarama hatası", isPresented: Binding(get: { error != nil }, set: { if !$0 { error = nil } })) {
            Button("Tamam") { error = nil }
        } message: { Text(error ?? "") }
        .confirmationDialog("Taramadan ayrılmak istiyor musun?", isPresented: $showExitConfirm) {
            Button("İptal", role: .cancel) {}
            Button("Taramaya devam et") { step = .capture }
            Button("Taramayı kaydet", action: finish)
        } message: { Text("Kaydedilmiş fotoğrafların silinmesini önlemek için önce oturumu tamamla.") }
    }

    private func finish() {
        guard let project, !stopping else { return }
        stopping = true
        engine.finish { result in
            stopping = false
            switch result {
            case .success(let values):
                do {
                    try store.complete(project.id, frames: values.frames, points: values.points, elapsed: values.seconds)
                    step = .summary
                } catch { self.error = "Oturum kaydı doğrulanamadı: \(error.localizedDescription)" }
            case .failure(let error): self.error = error.localizedDescription
            }
        }
    }
}

// 06 New scan settings. Photo-only capture not advertised as implemented.
struct NewScanScreen: View {
    let create: (String, ScanTarget) -> Void
    let cancel: () -> Void
    @State private var name = ""
    @State private var target: ScanTarget = .small

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                SectionTitle(text: "Yeni Tarama")
                Text("Proje Adı").font(.headline)
                TextField("Örn. Heykel, masa, oda köşesi", text: $name)
                    .textInputAutocapitalization(.sentences)
                    .autocorrectionDisabled()
                    .padding(14).background(MS.panel, in: RoundedRectangle(cornerRadius: 12))
                    .accessibilityIdentifier("projectName")
                Text("Nesne Türü").font(.headline)
                HStack(spacing: 8) {
                    ForEach(ScanTarget.allCases) { option in
                        Button { target = option } label: {
                            VStack(spacing: 10) {
                                Image(systemName: option.symbol).font(.title2)
                                Text(option.rawValue).font(.caption2).multilineTextAlignment(.center)
                            }
                            .frame(maxWidth: .infinity, minHeight: 90)
                            .background(target == option ? MS.cyan : MS.panel,
                                        in: RoundedRectangle(cornerRadius: 12))
                            .foregroundStyle(target == option ? Color.black : .white)
                        }.accessibilityAddTraits(target == option ? [.isSelected] : [])
                    }
                }
                Text("Çekim Modu").font(.headline)
                MSCard {
                    Label("Kamera + ARKit", systemImage: "viewfinder").fontWeight(.semibold)
                    Text("Fotoğraflar ve mevcut kamera pozları kaydedilir.").font(.caption).foregroundStyle(MS.muted)
                }
                MSCard {
                    HStack { Label("Fotoğraf Dizisi", systemImage: "photo.stack"); Spacer(); Text("Sonraki sürüm").font(.caption).foregroundStyle(MS.muted) }
                }.opacity(0.55)
                Notice(text: "Farklı açılardan 30–60 fotoğraf önerilir; rekonstrüksiyon garantisi değildir.")
                Notice(text: "Tam 3D model Windows üzerinde oluşturulur.")
                MSButton(title: "Çekime Geç", systemImage: "arrow.right") { create(name, target) }
                    .disabled((try? ScanContract.validateProjectName(name)) == nil)
                    .opacity((try? ScanContract.validateProjectName(name)) == nil ? 0.5 : 1)
                MSButton(title: "İptal", prominent: false, action: cancel)
            }.padding(20)
        }.msScreen()
    }
}

// 07 Permissions, no invented independent motion sensor permission.
struct PermissionsScreen: View {
    let back: () -> Void
    let start: () -> Void
    @State private var authorization = AVCaptureDevice.authorizationStatus(for: .video)
    private var arSupported: Bool { ARWorldTrackingConfiguration.isSupported }
    private var canProceed: Bool { authorization == .authorized && arSupported }

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text("Çekim Hazırlığı").font(.title2.bold())
            MSCard {
                Label("Kamera Erişimi", systemImage: "camera").font(.headline)
                Text(authorization == .authorized ? "İzin verildi" : "Fotoğraf çekmek için kamera erişimi gerekli.")
                    .foregroundStyle(MS.muted)
                if authorization == .notDetermined {
                    MSButton(title: "Kamera İzni Ver") {
                        AVCaptureDevice.requestAccess(for: .video) { _ in
                            DispatchQueue.main.async { authorization = AVCaptureDevice.authorizationStatus(for: .video) }
                        }
                    }
                } else if authorization != .authorized {
                    MSButton(title: "Ayarları Aç") {
                        if let url = URL(string: UIApplication.openSettingsURLString) { UIApplication.shared.open(url) }
                    }
                }
            }
            MSCard {
                Label("ARKit Takibi", systemImage: "cube.transparent").font(.headline)
                Text(arSupported ? "Cihaz uyumlu; takip çekim sırasında doğrulanır." : "Bu cihaz ARKit world tracking desteklemiyor.")
                    .foregroundStyle(MS.muted)
            }
            Notice(text: "Fotoğraflar cihaz üzerinde tutulur. Paylaşım için fotoğraf arşivine erişim gerekmez.")
            Spacer()
            MSButton(title: "Kamera Aç", systemImage: "arrow.right", action: start)
                .disabled(!canProceed).opacity(canProceed ? 1 : 0.5)
            MSButton(title: "Geri Dön", prominent: false, action: back)
        }
        .padding(20).msScreen()
        .onAppear { authorization = AVCaptureDevice.authorizationStatus(for: .video) }
    }
}

// 08 Live ARKit capture, no simulated depth view.
struct CaptureScreen: View {
    @AppStorage("monoscan11.captureTips") private var captureTips = true
    @ObservedObject var engine: ScanEngine
    let folder: URL
    let name: String
    let close: () -> Void
    let review: () -> Void
    @State private var started = false

    var body: some View {
        ZStack {
            ARCameraPreview(engine: engine).ignoresSafeArea()
            Color.black.opacity(0.14).ignoresSafeArea().allowsHitTesting(false)
            VStack(spacing: 12) {
                HStack {
                    Button(action: close) { Image(systemName: "xmark").font(.headline).frame(width: 44, height: 44) }
                    Spacer()
                    Text(name).lineLimit(1).font(.headline)
                    Spacer()
                    Button(action: review) { Image(systemName: "info.circle").frame(width: 44, height: 44) }
                }
                HStack {
                    Label("Takip: \(engine.tracking)", systemImage: "checkmark.circle")
                    Spacer()
                    Text("Kare: \(engine.imageCount)").monospacedDigit()
                }.font(.caption.bold()).padding(10).background(.black.opacity(0.65), in: RoundedRectangle(cornerRadius: 12))
                Spacer()
                Image(systemName: "viewfinder").font(.system(size: 132, weight: .ultraLight))
                    .foregroundStyle(MS.cyan.opacity(0.75)).accessibilityHidden(true)
                Spacer()
                if captureTips {
                    Text("Nesnenin çevresinden yavaşça ilerle").font(.footnote.bold())
                        .padding(10).background(.black.opacity(0.66), in: RoundedRectangle(cornerRadius: 8))
                }
                HStack {
                    Image(systemName: "photo").frame(width: 54, height: 54)
                    Spacer()
                    Button(action: engine.takePhoto) {
                        Circle().fill(.white).frame(width: 66, height: 66)
                            .padding(5).overlay(Circle().stroke(.white, lineWidth: 3))
                    }
                    .disabled(!engine.scanning)
                    .accessibilityLabel("Fotoğraf çek")
                    Spacer()
                    Button(action: review) {
                        VStack { Image(systemName: "checkmark.circle").font(.title); Text("Bitir").font(.caption) }
                            .frame(width: 54, height: 54)
                    }.disabled(engine.imageCount == 0)
                }.padding(.horizontal, 12)
                Text(engine.message).font(.caption).multilineTextAlignment(.center)
                    .padding(10).frame(maxWidth: .infinity)
                    .background(.black.opacity(0.66), in: RoundedRectangle(cornerRadius: 12))
            }.padding(16)
        }
        .foregroundStyle(.white)
        .onAppear {
            guard !started else { return }
            started = true
            engine.begin(in: folder)
        }
    }
}

private struct ARCameraPreview: UIViewRepresentable {
    let engine: ScanEngine
    func makeUIView(context: Context) -> ARSCNView {
        let scene = ARSCNView(frame: .zero)
        scene.automaticallyUpdatesLighting = true
        scene.debugOptions = []
        engine.attach(to: scene)
        return scene
    }
    func updateUIView(_ view: ARSCNView, context: Context) {}
    static func dismantleUIView(_ view: ARSCNView, coordinator: ()) { view.session.pause() }
}

// 09 Review. No fake blur/overlap scores; user can return before stopping.
struct QualityScreen: View {
    @ObservedObject var engine: ScanEngine
    let back: () -> Void
    let finish: () -> Void
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text("Çekim Kontrolü").font(.title2.bold())
            MSCard {
                Label("Kaydedilen fotoğraf: \(engine.imageCount)", systemImage: "photo.stack")
                Text("Fotoğraflar 3D rekonstrüksiyon için Windows'a aktarılacak.").font(.footnote).foregroundStyle(MS.muted)
            }
            MSCard {
                Label("Takip: \(engine.tracking)", systemImage: "viewfinder")
                Text("Sınırlı takip sırasında hareketi yavaşlat ve dokulu yüzeyleri kadraja al.")
                    .font(.footnote).foregroundStyle(MS.muted)
            }
            Notice(text: "Kapsama, bulanıklık ve örtüşme yüzdesi ölçülmedi; sahte kalite puanı gösterilmez.")
            Spacer()
            MSButton(title: "Çekime Dön", systemImage: "arrow.uturn.backward", action: back)
            MSButton(title: "Mevcut Çekimle Devam Et", prominent: false, action: finish)
                .disabled(engine.imageCount == 0)
        }.padding(20).msScreen()
    }
}

// 10 Summary, values from locally persisted project only.
struct SummaryScreen: View {
    @ObservedObject var store: ScanStore
    let id: UUID
    let finish: () -> Void
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                Text("Çekim Özeti").font(.title2.bold())
                if let project = store.item(id) {
                    SectionTitle(text: project.name)
                    MSCard {
                        Label("Görüntüler kaydedildi", systemImage: "checkmark.circle.fill").foregroundStyle(.green)
                        metric("Toplam fotoğraf", "\(project.imageCount)")
                        metric("Çekim süresi", String(format: "%.0f saniye", project.captureSeconds))
                        metric("Seyrek nokta", "\(project.pointCount)")
                    }
                    Notice(text: "Bu ekran 3D model sonucu değildir. Rekonstrüksiyon Windows'ta yapılır.")
                    NavigationLink(value: ProjectRoute.gallery(id)) { actionLabel("Kareleri İncele") }
                    if project.pointCount > 0 {
                        NavigationLink(value: ProjectRoute.preview(id)) { actionLabel("Seyrek Önizleme") }
                    } else { Notice(text: "Seyrek önizleme: oturumda özellik noktası kaydedilmedi.") }
                    NavigationLink(value: ProjectRoute.export(id)) { actionLabel("Dışa Aktar", primary: true) }
                }
                MSButton(title: "Projeye Dön", prominent: false, action: finish)
            }.padding(20)
        }.msScreen()
    }
}

func metric(_ label: String, _ value: String) -> some View {
    HStack { Text(label).foregroundStyle(MS.muted); Spacer(); Text(value).monospacedDigit() }
}

func actionLabel(_ name: String, primary: Bool = false) -> some View {
    Text(name).fontWeight(.semibold).frame(maxWidth: .infinity, minHeight: 51)
        .foregroundStyle(primary ? Color.black : Color.white)
        .background(primary ? MS.cyan : MS.panel2, in: RoundedRectangle(cornerRadius: 12))
}
