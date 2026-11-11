import AVFoundation
import Foundation

enum ImportError: LocalizedError {
    case unzip(String), noMaps, noAudio(String), unsupported(String)
    var errorDescription: String? {
        switch self {
        case .unzip(let m): return "Не удалось распаковать .osz: \(m)"
        case .noMaps: return "В архиве нет карт в режиме кружков"
        case .noAudio(let f): return "Рядом с картой нет аудиофайла «\(f)»"
        case .unsupported(let ext): return "Формат «.\(ext)» не поддерживается"
        }
    }
}

/// Песни лежат в «Application Support/TnQkoMusically/Songs/<папка>/» — аудио, картинки и .osu, как в osu!.
final class Library {
    static let audioExtensions: Set<String> = ["mp3", "m4a", "aac", "wav", "aif", "aiff", "flac", "caf", "mp4"]

    let root: URL
    private(set) var maps: [Beatmap] = []
    private(set) var skipped: [String] = []

    static var defaultRoot: URL {
        FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("TnQkoMusically", isDirectory: true)
    }

    init(root: URL = Library.defaultRoot) {
        self.root = root
        try? FileManager.default.createDirectory(at: songsDir, withIntermediateDirectories: true)
    }

    var songsDir: URL { root.appendingPathComponent("Songs", isDirectory: true) }

    func scan() {
        let fm = FileManager.default
        var found: [Beatmap] = []
        var bad: [String] = []
        let folders = (try? fm.contentsOfDirectory(at: songsDir, includingPropertiesForKeys: nil, options: [.skipsHiddenFiles])) ?? []
        for folder in folders {
            let files = (try? fm.contentsOfDirectory(at: folder, includingPropertiesForKeys: nil, options: [.skipsHiddenFiles])) ?? []
            for file in files where file.pathExtension.lowercased() == "osu" {
                do {
                    let map = try OsuParser.parse(url: file)
                    if !map.objects.isEmpty { found.append(map) }
                } catch {
                    bad.append(file.lastPathComponent)
                }
            }
        }
        found.sort {
            let a = ($0.displayArtist.lowercased(), $0.displayTitle.lowercased()), b = ($1.displayArtist.lowercased(), $1.displayTitle.lowercased())
            if a != b { return a < b }
            return $0.stars < $1.stars
        }
        maps = found
        skipped = bad
    }

    static func kind(of url: URL) -> String { url.pathExtension.lowercased() }

    static func isImportable(_ url: URL) -> Bool {
        let ext = kind(of: url)
        return ext == "osz" || ext == "osu" || audioExtensions.contains(ext)
    }

    /// Свободная папка внутри Songs.
    func newFolder(_ name: String) -> URL {
        let clean = name.components(separatedBy: CharacterSet(charactersIn: "/:\\?*\"<>|")).joined(separator: " ")
            .trimmingCharacters(in: .whitespaces)
        let base = clean.isEmpty ? "Песня" : String(clean.prefix(80))
        var url = songsDir.appendingPathComponent(base, isDirectory: true)
        var n = 2
        while FileManager.default.fileExists(atPath: url.path) {
            url = songsDir.appendingPathComponent("\(base) (\(n))", isDirectory: true)
            n += 1
        }
        return url
    }

    /// Импорт .osz (zip): распаковка системным ditto.
    @discardableResult
    func importOsz(_ url: URL) throws -> URL {
        let dest = newFolder(url.deletingPathExtension().lastPathComponent)
        try FileManager.default.createDirectory(at: dest, withIntermediateDirectories: true)
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/usr/bin/ditto")
        p.arguments = ["-x", "-k", url.path, dest.path]
        let err = Pipe()
        p.standardError = err
        try p.run()
        p.waitUntilExit()
        if p.terminationStatus != 0 {
            let msg = String(data: err.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
            try? FileManager.default.removeItem(at: dest)
            throw ImportError.unzip(msg.trimmingCharacters(in: .whitespacesAndNewlines))
        }
        let maps = (try? FileManager.default.contentsOfDirectory(at: dest, includingPropertiesForKeys: nil))?
            .filter { $0.pathExtension.lowercased() == "osu" }
            .compactMap { try? OsuParser.parse(url: $0) } ?? []
        if maps.isEmpty {
            try? FileManager.default.removeItem(at: dest)
            throw ImportError.noMaps
        }
        return dest
    }

    /// Импорт отдельного .osu: копируем карту, её аудио и фон в новую папку.
    @discardableResult
    func importOsu(_ url: URL) throws -> URL {
        let map = try OsuParser.parse(url: url)
        let src = url.deletingLastPathComponent()
        guard let audio = map.audioURL, FileManager.default.fileExists(atPath: audio.path) else {
            throw ImportError.noAudio(map.audioFilename)
        }
        let dest = newFolder("\(map.artist) - \(map.title)")
        let fm = FileManager.default
        try fm.createDirectory(at: dest, withIntermediateDirectories: true)
        try fm.copyItem(at: url, to: dest.appendingPathComponent(url.lastPathComponent))
        try? fm.copyItem(at: audio, to: dest.appendingPathComponent(map.audioFilename))
        if let bg = map.background { try? fm.copyItem(at: src.appendingPathComponent(bg), to: dest.appendingPathComponent(bg)) }
        // остальные сложности той же песни
        for other in (try? fm.contentsOfDirectory(at: src, includingPropertiesForKeys: nil)) ?? []
        where other.pathExtension.lowercased() == "osu" && other != url {
            if let m = try? OsuParser.parse(url: other), m.audioFilename == map.audioFilename {
                try? fm.copyItem(at: other, to: dest.appendingPathComponent(other.lastPathComponent))
            }
        }
        return dest
    }

    /// Свой трек: копия в новую папку + три сгенерированные сложности.
    @discardableResult
    func importAudio(_ url: URL) throws -> URL {
        let meta = BeatGen.metadata(url)
        let analysis = try BeatGen.analyze(url)
        let dest = newFolder("\(meta.artist) - \(meta.title)")
        let fm = FileManager.default
        try fm.createDirectory(at: dest, withIntermediateDirectories: true)
        let audioName = "audio." + url.pathExtension.lowercased()
        try fm.copyItem(at: url, to: dest.appendingPathComponent(audioName))
        let seed = UInt64(truncatingIfNeeded: (meta.title + meta.artist).unicodeScalars.reduce(5381) { ($0 << 5) &+ $0 &+ Int($1.value) })
        for level in Level.allCases {
            let map = BeatGen.generate(analysis, level: level, audioFilename: audioName, title: meta.title, artist: meta.artist, seed: seed)
            let file = dest.appendingPathComponent("\(meta.artist) - \(meta.title) (TnQko) [\(level.title)].osu".replacingOccurrences(of: "/", with: " "))
            try OsuWriter.write(map).write(to: file, atomically: true, encoding: .utf8)
        }
        return dest
    }

    func importAny(_ url: URL) throws -> URL {
        let ext = Library.kind(of: url)
        if ext == "osz" { return try importOsz(url) }
        if ext == "osu" { return try importOsu(url) }
        if Library.audioExtensions.contains(ext) { return try importAudio(url) }
        throw ImportError.unsupported(ext)
    }

    func delete(_ map: Beatmap) {
        guard let file = map.fileURL else { return }
        try? FileManager.default.removeItem(at: file)
        if let folder = map.folder,
           let rest = try? FileManager.default.contentsOfDirectory(at: folder, includingPropertiesForKeys: nil),
           !rest.contains(where: { $0.pathExtension.lowercased() == "osu" }) {
            try? FileManager.default.removeItem(at: folder)
        }
    }
}

/// Настройки и рекорды.
final class Settings {
    static let shared = Settings(defaults: .standard)
    let defaults: UserDefaults

    init(defaults: UserDefaults) {
        self.defaults = defaults
        defaults.register(defaults: ["musicVolume": 0.8, "effectsVolume": 0.6, "offsetMs": 0.0, "dim": 0.7, "noFail": false, "cursorSize": 1.0, "mapColors": false])
    }

    var musicVolume: Float { get { defaults.float(forKey: "musicVolume") } set { defaults.set(newValue, forKey: "musicVolume") } }
    var effectsVolume: Float { get { defaults.float(forKey: "effectsVolume") } set { defaults.set(newValue, forKey: "effectsVolume") } }
    var offsetMs: Double { get { defaults.double(forKey: "offsetMs") } set { defaults.set(newValue, forKey: "offsetMs") } }
    var dim: Double { get { defaults.double(forKey: "dim") } set { defaults.set(newValue, forKey: "dim") } }
    var noFail: Bool { get { defaults.bool(forKey: "noFail") } set { defaults.set(newValue, forKey: "noFail") } }
    var mapColors: Bool { get { defaults.bool(forKey: "mapColors") } set { defaults.set(newValue, forKey: "mapColors") } }
    var cursorSize: Double { get { defaults.double(forKey: "cursorSize") } set { defaults.set(newValue, forKey: "cursorSize") } }

    struct Record {
        let score: Int, accuracy: Double, combo: Int, grade: String
    }

    func best(_ key: String) -> Record? {
        guard let d = (defaults.dictionary(forKey: "records") ?? [:])[key] as? [String: Any],
              let s = d["score"] as? Int else { return nil }
        return Record(score: s, accuracy: d["accuracy"] as? Double ?? 0, combo: d["combo"] as? Int ?? 0, grade: d["grade"] as? String ?? "D")
    }

    /// Сохраняет рекорд; true — если он новый.
    @discardableResult
    func submit(_ key: String, _ r: Record) -> Bool {
        if let old = best(key), old.score >= r.score { return false }
        var all = defaults.dictionary(forKey: "records") ?? [:]
        all[key] = ["score": r.score, "accuracy": r.accuracy, "combo": r.combo, "grade": r.grade]
        defaults.set(all, forKey: "records")
        return true
    }
}
