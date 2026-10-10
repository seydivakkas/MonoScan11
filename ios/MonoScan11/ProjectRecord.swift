import Foundation

// No sample records are injected: these are persisted user-created projects.
enum ScanTarget: String, Codable, CaseIterable, Identifiable {
    case small = "Küçük nesne"
    case large = "Büyük nesne"
    case room = "Mekân bölümü"
    var id: String { rawValue }
    var symbol: String {
        switch self { case .small: return "cube"; case .large: return "chair"; case .room: return "square.dashed.inset.filled" }
    }
}

enum ProjectPhase: String, Codable {
    case draft, completed, exported
    var title: String {
        switch self { case .draft: return "Taslak"; case .completed: return "Tamamlandı"; case .exported: return "Dışa aktarıldı" }
    }
}

struct ScanProject: Codable, Identifiable, Equatable {
    let id: UUID
    var name: String
    var target: ScanTarget
    let createdAt: Date
    var phase: ProjectPhase
    var imageCount: Int
    var pointCount: Int
    var captureSeconds: Double

    init(id: UUID = UUID(), name: String, target: ScanTarget, createdAt: Date = Date()) {
        self.id = id
        self.name = name
        self.target = target
        self.createdAt = createdAt
        self.phase = .draft
        self.imageCount = 0
        self.pointCount = 0
        self.captureSeconds = 0
    }
}

struct SessionFrame: Codable, Equatable {
    let file: String
    let timestamp: Double
    let width: Int
    let height: Int
    let intrinsics: [[Float]]
    let cameraToWorld: [[Float]]
}

struct SessionManifest: Codable {
    let schemaVersion: Int
    let acquisition: String
    let cameraImageCoordinates: String
    let cameraPoseConvention: String
    let frames: [SessionFrame]
    let sparsePointCount: Int
}

enum ScanDataError: LocalizedError {
    case invalidName, invalidSession, unsafePath, sizeLimit, noImages
    var errorDescription: String? {
        switch self {
        case .invalidName: return "Proje adı 1–80 karakter arasında olmalı."
        case .invalidSession: return "Oturum verisi eksik veya görüntülerle uyuşmuyor."
        case .unsafePath: return "Güvensiz dosya yolu reddedildi."
        case .sizeLimit: return "ZIP32 sınırı aşıldı (4 GiB / 65.535 dosya)."
        case .noImages: return "Dışa aktarmak için önce görüntü kaydet."
        }
    }
}

// Checked by both Swift tests and Windows Python contract tests.
enum ScanContract {
    static func validateProjectName(_ value: String) throws -> String {
        let name = value.trimmingCharacters(in: .whitespacesAndNewlines)
        guard (1...80).contains(name.count), !name.contains("/"), !name.contains("\\"),
              !name.unicodeScalars.contains(where: { CharacterSet.controlCharacters.contains($0) }) else {
            throw ScanDataError.invalidName
        }
        return name
    }

    static func validateManifest(_ manifest: SessionManifest, in folder: URL) throws {
        guard manifest.schemaVersion == 1, !manifest.frames.isEmpty else { throw ScanDataError.invalidSession }
        let images = folder.appendingPathComponent("images", isDirectory: true)
        let folderValues = try images.resourceValues(forKeys: [.isDirectoryKey, .isSymbolicLinkKey])
        guard folderValues.isDirectory == true, folderValues.isSymbolicLink != true else { throw ScanDataError.unsafePath }
        let names = try FileManager.default.contentsOfDirectory(atPath: images.path)
            .filter { $0.lowercased().hasSuffix(".jpg") || $0.lowercased().hasSuffix(".jpeg") || $0.lowercased().hasSuffix(".png") }
        guard names.count == manifest.frames.count,
              Set(names).count == names.count,
              Set(names) == Set(manifest.frames.map(\.file)) else { throw ScanDataError.invalidSession }
        for frame in manifest.frames {
            guard frame.file == URL(fileURLWithPath: frame.file).lastPathComponent,
                  !frame.file.contains("/"), !frame.file.contains("\\"),
                  frame.width > 0, frame.height > 0,
                  frame.intrinsics.count == 3,
                  frame.intrinsics.allSatisfy({ $0.count == 3 && $0.allSatisfy(\.isFinite) }),
                  frame.cameraToWorld.count == 4,
                  frame.cameraToWorld.allSatisfy({ $0.count == 4 && $0.allSatisfy(\.isFinite) }),
                  frame.timestamp.isFinite else { throw ScanDataError.invalidSession }
        }
        guard Swift.zip(manifest.frames, manifest.frames.dropFirst()).allSatisfy({ $0.0.timestamp < $0.1.timestamp }) else {
            throw ScanDataError.invalidSession
        }
    }
}
