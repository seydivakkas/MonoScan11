import Foundation

func check(_ condition: @autoclosure () -> Bool, _ message: String) {
    if !condition() { fputs("FAIL: \(message)\n", stderr); exit(1) }
}
let root = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
let temp = FileManager.default.temporaryDirectory.appendingPathComponent("monoscan-swift-\(UUID().uuidString)")
defer { try? FileManager.default.removeItem(at: temp) }
let scan = temp.appendingPathComponent("scan")
let images = scan.appendingPathComponent("images")
try FileManager.default.createDirectory(at: images, withIntermediateDirectories: true)
let fixture = root.appendingPathComponent("tests/fixtures/tiny8.jpg")
let sanitized = try ScanContract.validateProjectName("   Heykel  ")
check(sanitized == "Heykel", "trimmed name")
do {
    _ = try ScanContract.validateProjectName("../escape")
    check(false, "unsafe name accepted")
} catch ScanDataError.invalidName { } // expected
let K: [[Float]] = [[100,0,4],[0,100,4],[0,0,1]]
let pose: [[Float]] = [[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]
var frames: [SessionFrame] = []
for i in 1...3 {
    let name = String(format: "frame_%04d.jpg", i)
    try FileManager.default.copyItem(at: fixture, to: images.appendingPathComponent(name))
    frames.append(SessionFrame(file: name, timestamp: Double(i), width: 8, height: 8, intrinsics: K, cameraToWorld: pose))
}
let manifest = SessionManifest(schemaVersion: 1,
    acquisition: "ARKit world tracking: rear RGB + VIO, NOT LiDAR",
    cameraImageCoordinates: "Unrotated ARFrame.capturedImage pixels; image dimensions and K correspond to this buffer",
    cameraPoseConvention: "camera_to_world, row-major serialization, ARKit world coordinates (approximate meters)",
    frames: frames, sparsePointCount: 0)
try JSONEncoder().encode(manifest).write(to: scan.appendingPathComponent("session.json"))
let record = ScanProject(name: "Test", target: .small)
try JSONEncoder().encode(record).write(to: scan.appendingPathComponent("project.json"))
try ScanContract.validateManifest(manifest, in: scan)
let zip = temp.appendingPathComponent("result.zip")
try ZIPStore.export(projectFolder: scan, destination: zip)
check(FileManager.default.fileExists(atPath: zip.path), "ZIP produced")
do { try ZIPStore.export(projectFolder: scan, destination: zip); check(false, "overwrite allowed") }
catch { } // cannot clobber an earlier export
let bad = SessionManifest(schemaVersion: 1, acquisition: "", cameraImageCoordinates: "", cameraPoseConvention: "", frames: Array(frames.dropLast()), sparsePointCount: 0)
do { try ScanContract.validateManifest(bad, in: scan); check(false, "incomplete session accepted") }
catch ScanDataError.invalidSession { } // expected
let destination = CommandLine.arguments.dropFirst().first
if let destination { try FileManager.default.copyItem(at: zip, to: URL(fileURLWithPath: destination)) }
print("Swift core PASS: name validation, session contract, ZIP export, overwrite safety, mismatch rejection")
