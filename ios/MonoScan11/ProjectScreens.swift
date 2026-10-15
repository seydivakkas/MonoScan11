import SwiftUI
import SceneKit
import simd
import UIKit

// Shared destinations used by capture summary and persisted projects.
enum ProjectRoute: Hashable {
    case gallery(UUID), preview(UUID), export(UUID)
}

// 14 Projects
struct ProjectsScreen: View {
    @ObservedObject var store: ScanStore
    let newScan: () -> Void
    @State private var query = ""
    @State private var selection = "Tümü"

    private var shown: [ScanProject] {
        store.projects.filter { value in
            (query.isEmpty || value.name.localizedCaseInsensitiveContains(query)) &&
            (selection == "Tümü" || (selection == "Taslak" && value.phase == .draft) ||
             (selection == "Tamamlanan" && value.phase == .completed) ||
             (selection == "Dışa Aktarılan" && value.phase == .exported))
        }
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                HStack {
                    Text("Taramalar").font(.largeTitle.bold())
                    Spacer()
                    Button(action: newScan) { Image(systemName: "plus").font(.title2).frame(width: 44, height: 44) }
                        .accessibilityLabel("Yeni tarama")
                }
                TextField("Proje ara…", text: $query).padding(13)
                    .background(MS.panel, in: RoundedRectangle(cornerRadius: 12))
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack {
                        ForEach(["Tümü", "Taslak", "Tamamlanan", "Dışa Aktarılan"], id: \.self) { tag in
                            Button(tag) { selection = tag }
                                .font(.footnote).padding(.horizontal, 11).padding(.vertical, 8)
                                .background(selection == tag ? MS.cyan : MS.panel2, in: Capsule())
                                .foregroundStyle(selection == tag ? Color.black : Color.white)
                        }
                    }
                }
                if shown.isEmpty { Notice(text: "Bu filtre için proje bulunamadı.", symbol: "folder") }
                ForEach(shown) { item in
                    NavigationLink(value: item.id) { ProjectRow(project: item) }.buttonStyle(.plain)
                }
            }.padding(20)
        }.msScreen().navigationBarHidden(true)
    }
}

// 15 Project detail
struct ProjectDetailScreen: View {
    @ObservedObject var store: ScanStore
    let id: UUID
    @Environment(\.dismiss) private var dismiss
    @State private var showRename = false
    @State private var rename = ""
    @State private var showDelete = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                if let value = store.item(id) {
                    SectionTitle(text: value.name)
                    MSCard {
                        Label(value.target.rawValue, systemImage: value.target.symbol).font(.headline)
                        metric("Durum", value.phase.title)
                        metric("Fotoğraf", "\(value.imageCount)")
                        metric("Seyrek nokta", "\(value.pointCount)")
                        metric("Tarih", value.createdAt.formatted(date: .abbreviated, time: .shortened))
                    }
                    if value.imageCount > 0 {
                        NavigationLink(value: ProjectRoute.gallery(id)) { actionLabel("Fotoğraflar") }
                        if value.pointCount > 0 {
                            NavigationLink(value: ProjectRoute.preview(id)) { actionLabel("Seyrek Önizleme") }
                        } else { Notice(text: "Kayıtlı seyrek nokta bulunmuyor.") }
                        NavigationLink(value: ProjectRoute.export(id)) { actionLabel("Dışa Aktar", primary: true) }
                    } else { Notice(text: "Bu proje taslak. Henüz fotoğraf kaydedilmedi.") }
                    Button("Projeyi Yeniden Adlandır") { rename = value.name; showRename = true }
                    Button("Projeyi Sil", role: .destructive) { showDelete = true }
                } else { Notice(text: "Proje bulunamadı.") }
            }.padding(20)
        }
        .navigationTitle("Proje Detayı").navigationBarTitleDisplayMode(.inline).msScreen()
        .navigationDestination(for: ProjectRoute.self) { route in
            switch route {
            case .gallery(let value): GalleryScreen(store: store, id: value)
            case .preview(let value): SparseScreen(store: store, id: value)
            case .export(let value): ExportScreen(store: store, id: value)
            }
        }
        .alert("Proje adını değiştir", isPresented: $showRename) {
            TextField("Proje adı", text: $rename)
            Button("Kaydet") {
                do { try store.rename(id, to: rename) }
                catch { store.lastError = error.localizedDescription }
            }
            Button("İptal", role: .cancel) {}
        }
        .confirmationDialog("Proje ve bütün fotoğrafları silinsin mi?", isPresented: $showDelete, titleVisibility: .visible) {
            Button("Kalıcı olarak sil", role: .destructive) {
                do { try store.delete(id); dismiss() }
                catch { store.lastError = error.localizedDescription }
            }
        } message: { Text("Bu işlem geri alınamaz.") }
    }
}

// 11 Gallery. Deletion is explicitly deferred until atomic frame/manifest editing is built.
struct GalleryScreen: View {
    @ObservedObject var store: ScanStore
    let id: UUID
    @State private var selectedImage: SelectedPhoto?
    private let columns = Array(repeating: GridItem(.flexible(), spacing: 8), count: 3)

    var body: some View {
        let images = store.images(id)
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                Text("\(images.count) kare • Zaman sıralı").foregroundStyle(MS.muted)
                if images.isEmpty { Notice(text: "Henüz fotoğraf kaydedilmedi.") }
                LazyVGrid(columns: columns, spacing: 8) {
                    ForEach(images, id: \.path) { file in
                        Button { selectedImage = SelectedPhoto(url: file) } label: {
                            Group {
                                if let image = UIImage(contentsOfFile: file.path) {
                                    Image(uiImage: image).resizable().scaledToFill()
                                } else { Image(systemName: "exclamationmark.triangle") }
                            }
                            .frame(height: 116).frame(maxWidth: .infinity)
                            .clipped().background(MS.panel2)
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                        }
                        .accessibilityLabel("Fotoğraf \(file.deletingPathExtension().lastPathComponent)")
                    }
                }
                Notice(text: "Kare silme, session.json ile atomik güncelleme tamamlanana kadar kapalıdır.")
            }.padding(16)
        }
        .navigationTitle("Fotoğraflar").navigationBarTitleDisplayMode(.inline).msScreen()
        .sheet(item: $selectedImage) { file in
            VStack(spacing: 12) {
                if let image = UIImage(contentsOfFile: file.url.path) {
                    Image(uiImage: image).resizable().scaledToFit()
                }
                Text(file.url.lastPathComponent).font(.caption).foregroundStyle(MS.muted)
                Button("Kapat") { selectedImage = nil }
            }.padding().msScreen()
        }
    }
}

struct SelectedPhoto: Identifiable {
    let url: URL
    var id: String { url.path }
}

// 12 Sparse preview; only real on-disk ASCII PLY vertices. No fabricated mesh.
struct SparseScreen: View {
    @ObservedObject var store: ScanStore
    let id: UUID
    @State private var scene: SCNScene?
    @State private var count = 0
    @State private var error: String?

    var body: some View {
        VStack(spacing: 14) {
            if let scene {
                SceneView(scene: scene, options: [.allowsCameraControl, .autoenablesDefaultLighting])
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .accessibilityLabel("Gerçek seyrek ARKit özellik noktaları")
                Text("\(count) seyrek nokta").monospacedDigit()
            } else {
                Spacer()
                Notice(text: error ?? "Seyrek önizleme için gerçek özellik noktası bulunmuyor.")
                Spacer()
            }
            Notice(text: "Bu bir yüzey modeli veya LiDAR derinlik haritası değildir.")
        }.padding(14)
        .navigationTitle("Seyrek Önizleme").navigationBarTitleDisplayMode(.inline).msScreen()
        .onAppear { loadPLY() }
    }

    private func loadPLY() {
        guard let url = store.pointCloud(id) else { return }
        do {
            let contents = try String(contentsOf: url, encoding: .utf8)
            let lines = contents.components(separatedBy: .newlines)
            guard let end = lines.firstIndex(of: "end_header"),
                  let countLine = lines.first(where: { $0.hasPrefix("element vertex ") }),
                  let expected = Int(countLine.split(separator: " ").last ?? ""),
                  expected > 0, expected <= 100_000 else { return }
            let vertices: [SCNVector3] = lines.dropFirst(end + 1).prefix(expected).compactMap { line in
                let parts = line.split(separator: " ")
                guard parts.count == 3, let x = Float(parts[0]), let y = Float(parts[1]), let z = Float(parts[2]),
                      x.isFinite, y.isFinite, z.isFinite else { return nil }
                return SCNVector3(x, y, z)
            }
            guard vertices.count == expected else { throw ScanDataError.invalidSession }
            let source = SCNGeometrySource(vertices: vertices)
            let indices = Array(Int32(0)..<Int32(expected))
            let element = SCNGeometryElement(indices: indices, primitiveType: .point)
            element.pointSize = 2.2
            let geometry = SCNGeometry(sources: [source], elements: [element])
            geometry.firstMaterial?.diffuse.contents = UIColor.cyan
            let display = SCNScene()
            display.rootNode.addChildNode(SCNNode(geometry: geometry))
            let minV = vertices.reduce(SIMD3<Float>(repeating: .infinity)) { v, p in
                simd_min(v, SIMD3(p.x, p.y, p.z))
            }
            let maxV = vertices.reduce(SIMD3<Float>(repeating: -.infinity)) { v, p in
                simd_max(v, SIMD3(p.x, p.y, p.z))
            }
            let center = (minV + maxV) / 2
            let radius = max(0.2, simd_length(maxV - minV))
            let camera = SCNNode()
            camera.camera = SCNCamera()
            camera.position = SCNVector3(center.x, center.y, center.z + radius * 1.5)
            camera.look(at: SCNVector3(center.x, center.y, center.z))
            display.rootNode.addChildNode(camera)
            count = expected
            scene = display
        } catch { self.error = "Nokta bulutu okunamadı: \(error.localizedDescription)" }
    }
}

// 13 ZIP export and explicit system share sheet.
struct ExportScreen: View {
    @ObservedObject var store: ScanStore
    let id: UUID
    @State private var url: URL?
    @State private var showShare = false
    @State private var error: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text("Dışa Aktar").font(.title2.bold())
            if let project = store.item(id) {
                SectionTitle(text: project.name)
                MSCard {
                    Label("Tarama Veri Paketi", systemImage: "shippingbox.fill").font(.headline)
                    Label("images/ — \(project.imageCount) fotoğraf", systemImage: "photo")
                    Label("session.json — Kare ve kamera verileri", systemImage: "doc.text")
                    Label("arkit_sparse.ply — Seyrek nokta kaydı", systemImage: "cube")
                    Label("project.json — Proje bilgileri", systemImage: "folder")
                }
            }
            Notice(text: "Paket Windows'a aktarılıp MonoScan11'in deneysel yerel SfM motoruyla işlenebilir. ZIP sıkıştırmasızdır.")
            if let url {
                Notice(text: "ZIP oluşturuldu: \(url.lastPathComponent)", symbol: "checkmark.circle")
                MSButton(title: "Dosyalara Kaydet / Paylaş", systemImage: "square.and.arrow.up") { showShare = true }
            } else { MSButton(title: "ZIP Paketi Oluştur", systemImage: "shippingbox") {
                do { url = try store.export(id) }
                catch { error = error.localizedDescription }
            } }
            Spacer()
        }.padding(20)
        .navigationTitle("Dışa Aktar").navigationBarTitleDisplayMode(.inline).msScreen()
        .sheet(isPresented: $showShare) {
            if let url { ShareSheet(items: [url]) }
        }
        .alert("Paket oluşturulamadı", isPresented: Binding(get: { error != nil }, set: { if !$0 { error = nil } })) {
            Button("Tamam") { error = nil }
        } message: { Text(error ?? "") }
    }
}

struct ShareSheet: UIViewControllerRepresentable {
    let items: [Any]
    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: items, applicationActivities: nil)
    }
    func updateUIViewController(_ controller: UIActivityViewController, context: Context) {}
}
