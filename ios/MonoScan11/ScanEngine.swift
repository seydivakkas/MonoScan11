import ARKit
import CoreImage
import Foundation
import SceneKit
import UIKit

// Manual capture of ARKit rear camera frames with VIO poses; never claims LiDAR depth.
// Queue confinement: session frames, pending flag, frame metadata and disk writes live on worker.
final class ScanEngine: NSObject, ObservableObject, ARSessionDelegate {
    @Published private(set) var scanning = false
    @Published private(set) var imageCount = 0
    @Published private(set) var pointCount = 0
    @Published private(set) var tracking = "Hazırlanıyor"
    @Published private(set) var message = "Telefonu nesneye doğrult."
    @Published private(set) var supported = ARWorldTrackingConfiguration.isSupported

    private let worker = DispatchQueue(label: "org.monoscan11.capture", qos: .utility)
    private let ciContext = CIContext()
    private var active = false
    private var pendingPhoto = false
    private var sessionDirectory: URL?
    private var frames: [SessionFrame] = []
    private var features: [UInt64: SIMD3<Float>] = [:]
    private var startDate: Date?
    private var lastPhotoTimestamp = -Double.infinity
    private var lastTrackingNotice = -Double.infinity

    func attach(to sceneView: ARSCNView) {
        guard supported else { message = "Bu cihaz ARKit world tracking desteklemiyor."; return }
        sceneView.session.delegateQueue = worker
        sceneView.session.delegate = self
        let configuration = ARWorldTrackingConfiguration()
        configuration.worldAlignment = .gravity
        configuration.planeDetection = [.horizontal, .vertical]
        // iPhone 11 has no rear LiDAR; no sceneDepth/frameSemantics enabled.
        sceneView.session.run(configuration)
    }

    func begin(in directory: URL) {
        guard supported, !scanning else { return }
        worker.async {
            guard !self.active else { return }
            do {
                try FileManager.default.createDirectory(at: directory.appendingPathComponent("images"), withIntermediateDirectories: true)
                self.sessionDirectory = directory
                self.frames = []
                self.features = [:]
                self.startDate = Date()
                self.lastPhotoTimestamp = -Double.infinity
                self.pendingPhoto = false
                self.active = true
                DispatchQueue.main.async {
                    self.scanning = true; self.imageCount = 0; self.pointCount = 0
                    self.message = "Deklanşöre basarak farklı açılardan fotoğraf kaydet."
                }
            } catch {
                DispatchQueue.main.async { self.message = "Kayıt hazırlanamadı: \(error.localizedDescription)" }
            }
        }
    }

    func takePhoto() {
        worker.async {
            guard self.active else { return }
            self.pendingPhoto = true
        }
    }

    func finish(completion: @escaping (Result<(frames: Int, points: Int, seconds: Double), Error>) -> Void) {
        worker.async {
            guard self.active else {
                DispatchQueue.main.async { completion(.failure(ScanDataError.noImages)) }
                return
            }
            self.pendingPhoto = false
            // Stay on worker to serialize the final manifest after prior photos.
            self.active = false
            do {
                guard !self.frames.isEmpty else { throw ScanDataError.noImages }
                try self.writeManifest()
                try self.writeSparsePLY()
                let result = (frames: self.frames.count, points: self.features.count, seconds: Date().timeIntervalSince(self.startDate ?? Date()))
                DispatchQueue.main.async {
                    self.scanning = false; self.pointCount = result.points
                    self.message = "Görüntüler kaydedildi. 3D model Windows'ta oluşturulur."
                    completion(.success(result))
                }
            } catch {
                DispatchQueue.main.async { self.scanning = false; self.message = error.localizedDescription; completion(.failure(error)) }
            }
        }
    }

    func session(_ session: ARSession, didUpdate frame: ARFrame) {
        if frame.timestamp - lastTrackingNotice >= 0.5 {
            let state: String
            switch frame.camera.trackingState {
            case .normal: state = "İyi"
            case .limited: state = "Sınırlı"
            case .notAvailable: state = "Kullanılamıyor"
            }
            lastTrackingNotice = frame.timestamp
            DispatchQueue.main.async { self.tracking = state }
        }
        guard active, pendingPhoto, let directory = sessionDirectory else { return }
        pendingPhoto = false
        guard frame.timestamp - lastPhotoTimestamp >= 0.25 else {
            DispatchQueue.main.async { self.message = "Bir sonraki kare için kısa süre bekle." }
            return
        }
        guard case .normal = frame.camera.trackingState else {
            DispatchQueue.main.async { self.message = "AR takibi sınırlı. Telefonu yavaşça hareket ettir." }
            return
        }
        guard frames.count < 150 else {
            DispatchQueue.main.async { self.message = "150 kare sınırına ulaşıldı. Taramayı bitir." }
            return
        }
        let image = CIImage(cvPixelBuffer: frame.capturedImage)
        guard let cg = ciContext.createCGImage(image, from: image.extent),
              let jpeg = UIImage(cgImage: cg).jpegData(compressionQuality: 0.88) else {
            DispatchQueue.main.async { self.message = "Fotoğraf kodlanamadı." }
            return
        }
        let name = String(format: "frame_%04d.jpg", frames.count + 1)
        do {
            try jpeg.write(to: directory.appendingPathComponent("images").appendingPathComponent(name), options: .atomic)
        } catch {
            DispatchQueue.main.async { self.message = "Fotoğraf yazılamadı: \(error.localizedDescription)" }
            return
        }
        let buffer = frame.capturedImage
        frames.append(SessionFrame(
            file: name, timestamp: frame.timestamp,
            width: CVPixelBufferGetWidth(buffer), height: CVPixelBufferGetHeight(buffer),
            intrinsics: matrixRows(frame.camera.intrinsics),
            cameraToWorld: matrixRows(frame.camera.transform)))
        if let cloud = frame.rawFeaturePoints {
            for (point, id) in zip(cloud.points, cloud.identifiers) {
                if features.count >= 100_000 { break }
                features[id] = point
            }
        }
        lastPhotoTimestamp = frame.timestamp
        let count = frames.count
        let totalPoints = features.count
        DispatchQueue.main.async {
            self.imageCount = count
            self.pointCount = totalPoints
            self.message = "Kare \(count) kaydedildi."
        }
    }

    private func writeManifest() throws {
        guard let folder = sessionDirectory else { throw ScanDataError.invalidSession }
        let manifest = SessionManifest(
            schemaVersion: 1,
            acquisition: "ARKit world tracking: rear RGB + VIO, NOT LiDAR",
            cameraImageCoordinates: "Unrotated ARFrame.capturedImage pixels; image dimensions and K correspond to this buffer",
            cameraPoseConvention: "camera_to_world, row-major serialization, ARKit world coordinates (approximate meters)",
            frames: frames, sparsePointCount: features.count)
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        try encoder.encode(manifest).write(to: folder.appendingPathComponent("session.json"), options: .atomic)
    }

    private func writeSparsePLY() throws {
        guard let folder = sessionDirectory else { throw ScanDataError.invalidSession }
        let prefix = """
        ply
        format ascii 1.0
        comment ARKit rawFeaturePoints - not LiDAR, not surface mesh
        element vertex \(features.count)
        property float x
        property float y
        property float z
        end_header

        """
        let rows = features.values.map { "\($0.x) \($0.y) \($0.z)" }.joined(separator: "\n")
        try (prefix + rows + "\n").write(to: folder.appendingPathComponent("arkit_sparse.ply"), atomically: true, encoding: .utf8)
    }
}

private func matrixRows(_ matrix: simd_float3x3) -> [[Float]] {
    [[matrix.columns.0.x, matrix.columns.1.x, matrix.columns.2.x],
     [matrix.columns.0.y, matrix.columns.1.y, matrix.columns.2.y],
     [matrix.columns.0.z, matrix.columns.1.z, matrix.columns.2.z]]
}
private func matrixRows(_ matrix: simd_float4x4) -> [[Float]] {
    [[matrix.columns.0.x, matrix.columns.1.x, matrix.columns.2.x, matrix.columns.3.x],
     [matrix.columns.0.y, matrix.columns.1.y, matrix.columns.2.y, matrix.columns.3.y],
     [matrix.columns.0.z, matrix.columns.1.z, matrix.columns.2.z, matrix.columns.3.z],
     [matrix.columns.0.w, matrix.columns.1.w, matrix.columns.2.w, matrix.columns.3.w]]
}
