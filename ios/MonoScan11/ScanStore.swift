import Foundation
import SwiftUI

@MainActor
final class ScanStore: ObservableObject {
    @Published private(set) var projects: [ScanProject] = []
    @Published var lastError: String?
    @Published private(set) var exporting = false
    @Published private(set) var lastExportURL: URL?

    private let fileManager = FileManager.default
    private let root: URL

    init(root: URL? = nil) {
        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first!
        self.root = root ?? docs.appendingPathComponent("Scans", isDirectory: true)
        reload()
    }

    func folder(for id: UUID) -> URL { root.appendingPathComponent(id.uuidString, isDirectory: true) }
    func item(_ id: UUID) -> ScanProject? { projects.first(where: { $0.id == id }) }

    func reload() {
        do {
            try fileManager.createDirectory(at: root, withIntermediateDirectories: true)
            let dirs = try fileManager.contentsOfDirectory(at: root, includingPropertiesForKeys: [.isDirectoryKey], options: [.skipsHiddenFiles])
            projects = dirs.compactMap { dir in
                let meta = dir.appendingPathComponent("project.json")
                guard dir.lastPathComponent == UUID(uuidString: dir.lastPathComponent)?.uuidString,
                      let data = try? Data(contentsOf: meta),
                      let record = try? JSONDecoder().decode(ScanProject.self, from: data),
                      record.id.uuidString == dir.lastPathComponent else { return nil }
                return record
            }.sorted { $0.createdAt > $1.createdAt }
        } catch { lastError = error.localizedDescription }
    }

    func create(name rawName: String, target: ScanTarget) throws -> ScanProject {
        let name = try ScanContract.validateProjectName(rawName)
        let record = ScanProject(name: name, target: target)
        let directory = folder(for: record.id)
        try fileManager.createDirectory(at: directory.appendingPathComponent("images", isDirectory: true), withIntermediateDirectories: true)
        do { try save(record) } catch { try? fileManager.removeItem(at: directory); throw error }
        projects.insert(record, at: 0)
        return record
    }

    func complete(_ id: UUID, frames: Int, points: Int, elapsed: Double) throws {
        guard var value = item(id) else { throw ScanDataError.invalidSession }
        let data = try Data(contentsOf: folder(for: id).appendingPathComponent("session.json"))
        let manifest = try JSONDecoder().decode(SessionManifest.self, from: data)
        try ScanContract.validateManifest(manifest, in: folder(for: id))
        guard manifest.frames.count == frames, manifest.sparsePointCount == points else { throw ScanDataError.invalidSession }
        value.phase = .completed
        value.imageCount = frames
        value.pointCount = points
        value.captureSeconds = elapsed
        try replace(value)
    }

    func rename(_ id: UUID, to raw: String) throws {
        guard var value = item(id) else { throw ScanDataError.invalidSession }
        value.name = try ScanContract.validateProjectName(raw)
        try replace(value)
    }

    func delete(_ id: UUID) throws {
        guard item(id) != nil else { return }
        try fileManager.removeItem(at: folder(for: id))
        projects.removeAll { $0.id == id }
    }

    func images(_ id: UUID) -> [URL] {
        let dir = folder(for: id).appendingPathComponent("images")
        return ((try? fileManager.contentsOfDirectory(at: dir, includingPropertiesForKeys: nil)) ?? [])
            .filter { ["jpg", "jpeg", "png"].contains($0.pathExtension.lowercased()) }
            .sorted { $0.lastPathComponent < $1.lastPathComponent }
    }

    func pointCloud(_ id: UUID) -> URL? {
        let path = folder(for: id).appendingPathComponent("arkit_sparse.ply")
        return fileManager.fileExists(atPath: path.path) ? path : nil
    }

    func export(_ id: UUID) throws -> URL {
        guard let value = item(id), value.phase != .draft else { throw ScanDataError.noImages }
        exporting = true
        defer { exporting = false }
        let dest = root.deletingLastPathComponent()
            .appendingPathComponent("Exports", isDirectory: true)
            .appendingPathComponent("\(id.uuidString)-\(UUID().uuidString.prefix(8)).zip")
        // New unique destination: failed attempts never destroy a previous export.
        try ZIPStore.export(projectFolder: folder(for: id), destination: dest)
        var updated = value
        updated.phase = .exported
        try replace(updated)
        lastExportURL = dest
        return dest
    }

    private func replace(_ value: ScanProject) throws {
        try save(value)
        if let index = projects.firstIndex(where: { $0.id == value.id }) { projects[index] = value }
    }

    private func save(_ value: ScanProject) throws {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        try encoder.encode(value).write(to: folder(for: value.id).appendingPathComponent("project.json"), options: .atomic)
    }
}
