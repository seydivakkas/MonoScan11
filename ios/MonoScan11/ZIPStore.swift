import Foundation

// A small, dependency-free ZIP *store* encoder (method 0). Files are streamed,
// not compressed, to keep memory bounded. CRC32 and central directory are standard ZIP32.
// Not an importer: untrusted ZIP extraction is deliberately not implemented.
enum ZIPStore {
    static func export(projectFolder: URL, destination: URL) throws {
        let manager = FileManager.default
        let manifestURL = projectFolder.appendingPathComponent("session.json")
        let manifest = try JSONDecoder().decode(SessionManifest.self, from: Data(contentsOf: manifestURL))
        try ScanContract.validateManifest(manifest, in: projectFolder)
        let frameFiles = manifest.frames.map { "images/" + $0.file }.sorted()
        let optional = ["project.json", "arkit_sparse.ply"].filter {
            manager.fileExists(atPath: projectFolder.appendingPathComponent($0).path)
        }
        let names = ["session.json"] + optional + frameFiles
        guard names.count <= Int(UInt16.max) else { throw ScanDataError.sizeLimit }
        let directory = destination.deletingLastPathComponent()
        try manager.createDirectory(at: directory, withIntermediateDirectories: true)
        guard !manager.fileExists(atPath: destination.path) else { throw CocoaError(.fileWriteFileExists) }
        let temporary = directory.appendingPathComponent(".\(UUID().uuidString).zip.tmp")
        guard manager.createFile(atPath: temporary.path, contents: nil) else {
            throw CocoaError(.fileWriteUnknown)
        }
        defer { try? manager.removeItem(at: temporary) }
        let output = try FileHandle(forWritingTo: temporary)
        defer { try? output.close() }
        var entries: [CentralEntry] = []
        var position: UInt64 = 0
        for name in names {
            guard name.utf8.count <= 65535, !name.contains(".."), !name.hasPrefix("/"), !name.contains("\\") else {
                throw ScanDataError.unsafePath
            }
            let file = projectFolder.appendingPathComponent(name)
            let values = try file.resourceValues(forKeys: [.isRegularFileKey, .isSymbolicLinkKey, .fileSizeKey])
            guard values.isRegularFile == true, values.isSymbolicLink != true else { throw ScanDataError.unsafePath }
            let size = UInt64(values.fileSize ?? 0)
            guard size <= UInt64(UInt32.max), position + size + 65536 < UInt64(UInt32.max) else {
                throw ScanDataError.sizeLimit
            }
            let crc = try checksum(of: file)
            let filename = Data(name.utf8)
            var local = Data()
            local.appendLE(UInt32(0x04034B50)); local.appendLE(UInt16(20))
            local.appendLE(UInt16(0x0800)); local.appendLE(UInt16(0)) // UTF-8, stored
            local.appendLE(UInt16(0)); local.appendLE(UInt16(0)) // DOS time and date
            local.appendLE(crc); local.appendLE(UInt32(size)); local.appendLE(UInt32(size))
            local.appendLE(UInt16(filename.count)); local.appendLE(UInt16(0))
            local.append(filename)
            try output.write(contentsOf: local)
            let offset = UInt32(position)
            position += UInt64(local.count)
            let input = try FileHandle(forReadingFrom: file)
            defer { try? input.close() }
            while true {
                let chunk = try input.read(upToCount: 1024 * 1024) ?? Data()
                if chunk.isEmpty { break }
                try output.write(contentsOf: chunk)
                position += UInt64(chunk.count)
            }
            entries.append(CentralEntry(name: filename, size: UInt32(size), crc: crc, offset: offset))
        }
        let centralOffset = position
        for entry in entries {
            var row = Data()
            row.appendLE(UInt32(0x02014B50))
            row.appendLE(UInt16(20)); row.appendLE(UInt16(20))
            row.appendLE(UInt16(0x0800)); row.appendLE(UInt16(0))
            row.appendLE(UInt16(0)); row.appendLE(UInt16(0))
            row.appendLE(entry.crc); row.appendLE(entry.size); row.appendLE(entry.size)
            row.appendLE(UInt16(entry.name.count)); row.appendLE(UInt16(0)); row.appendLE(UInt16(0))
            row.appendLE(UInt16(0)); row.appendLE(UInt16(0)); row.appendLE(UInt32(0))
            row.appendLE(entry.offset); row.append(entry.name)
            try output.write(contentsOf: row)
            position += UInt64(row.count)
        }
        guard position < UInt64(UInt32.max) else { throw ScanDataError.sizeLimit }
        var end = Data()
        end.appendLE(UInt32(0x06054B50)); end.appendLE(UInt16(0)); end.appendLE(UInt16(0))
        end.appendLE(UInt16(entries.count)); end.appendLE(UInt16(entries.count))
        end.appendLE(UInt32(position - centralOffset)); end.appendLE(UInt32(centralOffset))
        end.appendLE(UInt16(0))
        try output.write(contentsOf: end)
        try output.synchronize()
        try manager.moveItem(at: temporary, to: destination)
    }

    private struct CentralEntry {
        let name: Data
        let size: UInt32
        let crc: UInt32
        let offset: UInt32
    }

    private static let table: [UInt32] = (0..<256).map { n in
        var x = UInt32(n)
        for _ in 0..<8 { x = x & 1 == 1 ? (x >> 1) ^ 0xEDB88320 : x >> 1 }
        return x
    }

    private static func checksum(of file: URL) throws -> UInt32 {
        let reader = try FileHandle(forReadingFrom: file)
        defer { try? reader.close() }
        var crc: UInt32 = 0xFFFF_FFFF
        while true {
            let data = try reader.read(upToCount: 1024 * 1024) ?? Data()
            if data.isEmpty { break }
            for byte in data { crc = (crc >> 8) ^ table[Int((crc ^ UInt32(byte)) & 0xFF)] }
        }
        return crc ^ 0xFFFF_FFFF
    }
}

private extension Data {
    mutating func appendLE(_ v: UInt16) {
        append(UInt8(truncatingIfNeeded: v)); append(UInt8(truncatingIfNeeded: v >> 8))
    }
    mutating func appendLE(_ v: UInt32) {
        append(UInt8(truncatingIfNeeded: v)); append(UInt8(truncatingIfNeeded: v >> 8))
        append(UInt8(truncatingIfNeeded: v >> 16)); append(UInt8(truncatingIfNeeded: v >> 24))
    }
}
