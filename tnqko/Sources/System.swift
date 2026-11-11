import AppKit
import AVFoundation
import IOKit.ps

/// Питание: работает ли Mac от батареи.
enum PowerSource {
    static func onBattery() -> Bool {
        guard let snapshot = IOPSCopyPowerSourcesInfo()?.takeRetainedValue(),
              let type = IOPSGetProvidingPowerSourceType(snapshot)?.takeUnretainedValue() else { return false }
        return (type as String) == kIOPSBatteryPowerValue
    }
}

/// Автозапуск через LaunchAgent (SMAppService появился только в macOS 13).
enum LoginItem {
    static let label = "com.tearsmilk.tnqkowallpaper"

    static var plistURL: URL {
        FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/LaunchAgents/\(label).plist")
    }

    static var isEnabled: Bool { FileManager.default.fileExists(atPath: plistURL.path) }

    static func setEnabled(_ on: Bool) throws {
        if on {
            guard let exe = Bundle.main.executablePath else { return }
            let plist: [String: Any] = [
                "Label": label,
                "ProgramArguments": [exe, "--login"],
                "RunAtLoad": true,
                "LimitLoadToSessionType": "Aqua",
                "ProcessType": "Interactive",
            ]
            try FileManager.default.createDirectory(at: plistURL.deletingLastPathComponent(), withIntermediateDirectories: true)
            let data = try PropertyListSerialization.data(fromPropertyList: plist, format: .xml, options: 0)
            try data.write(to: plistURL, options: .atomic)
        } else if isEnabled {
            try FileManager.default.removeItem(at: plistURL)
        }
    }
}

/// Превью видео (кадр через AVAssetImageGenerator) с кэшем.
final class Thumbnails {
    static let shared = Thumbnails()

    private var cache: [URL: NSImage] = [:]
    private let queue = DispatchQueue(label: "tnqko.thumbnails", qos: .userInitiated)

    func image(for url: URL, completion: @escaping (NSImage?) -> Void) {
        if let img = cache[url] { completion(img); return }
        queue.async {
            let cg = Thumbnails.make(url, maxSize: CGSize(width: 480, height: 270))
            DispatchQueue.main.async {
                let img = cg.map { NSImage(cgImage: $0, size: NSSize(width: $0.width, height: $0.height)) }
                if let img = img { self.cache[url] = img }
                completion(img)
            }
        }
    }

    static func make(_ url: URL, maxSize: CGSize, at seconds: Double = 1) -> CGImage? {
        let asset = AVURLAsset(url: url)
        let gen = AVAssetImageGenerator(asset: asset)
        gen.appliesPreferredTrackTransform = true
        gen.maximumSize = maxSize
        gen.requestedTimeToleranceBefore = .positiveInfinity
        gen.requestedTimeToleranceAfter = .positiveInfinity
        let duration = CMTimeGetSeconds(asset.duration)
        let t = duration.isFinite && duration > 0 ? min(seconds, duration / 2) : 0
        return try? gen.copyCGImage(at: CMTime(seconds: t, preferredTimescale: 600), actualTime: nil)
    }

    static func duration(_ url: URL) -> Double {
        let d = CMTimeGetSeconds(AVURLAsset(url: url).duration)
        return d.isFinite ? d : 0
    }
}
