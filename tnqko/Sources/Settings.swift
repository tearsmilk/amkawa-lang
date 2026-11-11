import AVFoundation
import Foundation

enum FillMode: String, CaseIterable {
    case fill, fit, stretch

    var title: String {
        switch self {
        case .fill: return "Заполнить экран"
        case .fit: return "Вписать целиком"
        case .stretch: return "Растянуть"
        }
    }

    var gravity: AVLayerVideoGravity {
        switch self {
        case .fill: return .resizeAspectFill
        case .fit: return .resizeAspect
        case .stretch: return .resize
        }
    }
}

enum DisplayMode: String, CaseIterable {
    case all, main

    var title: String { self == .all ? "На всех экранах" : "Только на главном" }
}

/// Настройки и библиотека видео (UserDefaults).
final class Settings {
    static let shared = Settings(defaults: .standard)

    static let videoExtensions: Set<String> = ["mp4", "mov", "m4v", "qt"]

    private enum K {
        static let library = "library", current = "current", sound = "sound", volume = "volume"
        static let fill = "fillMode", display = "displayMode", paused = "paused"
        static let pauseBattery = "pauseOnBattery", pauseCovered = "pauseWhenCovered"
        static let staticWallpaper = "staticWallpaper", originalWallpaper = "originalWallpaper"
    }

    let defaults: UserDefaults

    init(defaults: UserDefaults) {
        self.defaults = defaults
        defaults.register(defaults: [
            K.sound: false, K.volume: 0.5, K.fill: FillMode.fill.rawValue, K.display: DisplayMode.all.rawValue,
            K.paused: false, K.pauseBattery: true, K.pauseCovered: true, K.staticWallpaper: true,
        ])
    }

    var library: [URL] {
        get { (defaults.stringArray(forKey: K.library) ?? []).map { URL(fileURLWithPath: $0) } }
        set { defaults.set(newValue.map { $0.path }, forKey: K.library) }
    }

    var current: URL? {
        get { defaults.string(forKey: K.current).map { URL(fileURLWithPath: $0) } }
        set { defaults.set(newValue?.path, forKey: K.current) }
    }

    var sound: Bool {
        get { defaults.bool(forKey: K.sound) }
        set { defaults.set(newValue, forKey: K.sound) }
    }

    var volume: Float {
        get { defaults.float(forKey: K.volume) }
        set { defaults.set(max(0, min(1, newValue)), forKey: K.volume) }
    }

    var fillMode: FillMode {
        get { FillMode(rawValue: defaults.string(forKey: K.fill) ?? "") ?? .fill }
        set { defaults.set(newValue.rawValue, forKey: K.fill) }
    }

    var displayMode: DisplayMode {
        get { DisplayMode(rawValue: defaults.string(forKey: K.display) ?? "") ?? .all }
        set { defaults.set(newValue.rawValue, forKey: K.display) }
    }

    var paused: Bool {
        get { defaults.bool(forKey: K.paused) }
        set { defaults.set(newValue, forKey: K.paused) }
    }

    var pauseOnBattery: Bool {
        get { defaults.bool(forKey: K.pauseBattery) }
        set { defaults.set(newValue, forKey: K.pauseBattery) }
    }

    var pauseWhenCovered: Bool {
        get { defaults.bool(forKey: K.pauseCovered) }
        set { defaults.set(newValue, forKey: K.pauseCovered) }
    }

    /// Ставить кадр видео обычными обоями (видно в Mission Control и после выхода из программы).
    var staticWallpaper: Bool {
        get { defaults.bool(forKey: K.staticWallpaper) }
        set { defaults.set(newValue, forKey: K.staticWallpaper) }
    }

    /// Обои, которые стояли до первого запуска, — их возвращает «Убрать обои».
    var originalWallpaper: URL? {
        get { defaults.string(forKey: K.originalWallpaper).map { URL(fileURLWithPath: $0) } }
        set { defaults.set(newValue?.path, forKey: K.originalWallpaper) }
    }

    /// Добавляет видео без дублей, возвращает реально добавленные.
    @discardableResult
    func addToLibrary(_ urls: [URL]) -> [URL] {
        var lib = library
        var known = Set(lib.map { $0.standardizedFileURL.path })
        var added: [URL] = []
        for url in urls {
            let path = url.standardizedFileURL.path
            if known.insert(path).inserted {
                lib.append(url.standardizedFileURL)
                added.append(url.standardizedFileURL)
            }
        }
        library = lib
        return added
    }

    func removeFromLibrary(_ url: URL) {
        let path = url.standardizedFileURL.path
        library = library.filter { $0.standardizedFileURL.path != path }
    }

    static func hasVideoExtension(_ url: URL) -> Bool {
        videoExtensions.contains(url.pathExtension.lowercased())
    }
}
