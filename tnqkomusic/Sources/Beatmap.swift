import CoreGraphics
import Foundation

struct RGB: Equatable {
    var r: Double, g: Double, b: Double
    var cg: CGColor { CGColor(srgbRed: CGFloat(r), green: CGFloat(g), blue: CGFloat(b), alpha: 1) }
    func cg(alpha: Double) -> CGColor { CGColor(srgbRed: CGFloat(r), green: CGFloat(g), blue: CGFloat(b), alpha: CGFloat(alpha)) }
    func mixed(with o: RGB, _ t: Double) -> RGB { RGB(r: r + (o.r - r) * t, g: g + (o.g - g) * t, b: b + (o.b - b) * t) }

    static let defaults = [
        RGB(r: 0.851, g: 0.467, b: 0.341),  // терракота
        RGB(r: 0.949, g: 0.553, b: 0.698),  // розовый
        RGB(r: 0.608, g: 0.549, b: 1.0),    // сиреневый
        RGB(r: 0.424, g: 0.780, b: 0.722),  // мятный
    ]
}

struct TimingPoint {
    var time: Double
    var beatLength: Double
    var meter: Int
    var uninherited: Bool
    var kiai: Bool
}

enum HitKind { case circle, slider, spinner }

final class HitObject {
    let kind: HitKind
    let time: Double
    let pos: CGPoint
    let newCombo: Bool
    let comboSkip: Int
    let hitSound: Int
    var comboNumber = 1
    var colorIndex = 0
    // слайдер
    var curveType: Character = "L"
    var controlPoints: [CGPoint] = []
    var pixelLength: Double = 0
    var slides = 1
    var path: SliderPath?
    var spanDuration: Double = 0
    var endTime: Double

    init(kind: HitKind, time: Double, pos: CGPoint, newCombo: Bool, comboSkip: Int = 0, hitSound: Int = 0, endTime: Double? = nil) {
        self.kind = kind
        self.time = time
        self.pos = pos
        self.newCombo = newCombo
        self.comboSkip = comboSkip
        self.hitSound = hitSound
        self.endTime = endTime ?? time
    }

    var duration: Double { endTime - time }

    /// Позиция шара слайдера в момент t (мс) с учётом повторов.
    func sliderPosition(at t: Double) -> CGPoint {
        guard kind == .slider, let path = path, spanDuration > 0 else { return pos }
        let progress = max(0, min(Double(slides), (t - time) / spanDuration))
        var span = floor(progress)
        var f = progress - span
        if span >= Double(slides) { span = Double(slides - 1); f = 1 }
        return path.point(at: Int(span) % 2 == 1 ? 1 - f : f)
    }

    var endPosition: CGPoint { kind == .slider ? sliderPosition(at: endTime) : pos }
}

struct Difficulty {
    var hp = 5.0, cs = 4.0, od = 5.0, ar = 5.0
    var sliderMultiplier = 1.4, tickRate = 1.0

    /// Радиус кружка в osu!-пикселях (поле 512×384).
    var radius: Double { 54.4 - 4.48 * cs }
    /// Сколько мс кружок виден до удара.
    var preempt: Double { ar < 5 ? 1200 + 600 * (5 - ar) / 5 : 1200 - 750 * (ar - 5) / 5 }
    var fadeIn: Double { ar < 5 ? 800 + 400 * (5 - ar) / 5 : 800 - 500 * (ar - 5) / 5 }
    var window300: Double { 80 - 6 * od }
    var window100: Double { 140 - 8 * od }
    var window50: Double { 200 - 10 * od }
}

final class Beatmap {
    var fileURL: URL?
    var formatVersion = 14
    var audioFilename = ""
    var audioLeadIn = 0.0
    var previewTime = -1.0
    var mode = 0
    var title = "", titleUnicode = "", artist = "", artistUnicode = "", creator = "", version = "", source = "", tags = ""
    var background: String?
    var difficulty = Difficulty()
    var timingPoints: [TimingPoint] = []
    var comboColors: [RGB] = []
    var objects: [HitObject] = []

    var folder: URL? { fileURL?.deletingLastPathComponent() }
    var audioURL: URL? { audioFilename.isEmpty ? nil : folder?.appendingPathComponent(audioFilename) }
    var backgroundURL: URL? { background.flatMap { folder?.appendingPathComponent($0) } }
    var displayTitle: String { titleUnicode.isEmpty ? title : titleUnicode }
    var displayArtist: String { artistUnicode.isEmpty ? artist : artistUnicode }
    var colors: [RGB] { comboColors.isEmpty ? RGB.defaults : comboColors }

    /// Ключ для рекордов: «папка/файл».
    var key: String {
        guard let url = fileURL else { return title + version }
        return url.deletingLastPathComponent().lastPathComponent + "/" + url.lastPathComponent
    }

    var firstTime: Double { objects.first?.time ?? 0 }
    var endTime: Double { objects.map { $0.endTime }.max() ?? 0 }
    var drainSeconds: Double { max(0, endTime - firstTime) / 1000 }

    var bpm: Double {
        guard let tp = timingPoints.first(where: { $0.uninherited && $0.beatLength > 0 }) else { return 0 }
        return 60000 / tp.beatLength
    }

    var counts: (circles: Int, sliders: Int, spinners: Int) {
        var c = (0, 0, 0)
        for o in objects {
            switch o.kind {
            case .circle: c.0 += 1
            case .slider: c.1 += 1
            case .spinner: c.2 += 1
            }
        }
        return c
    }

    /// Грубая оценка сложности в «звёздах»: плотность объектов и средний прыжок.
    var stars: Double {
        guard objects.count > 1, drainSeconds > 0 else { return 0 }
        let density = Double(objects.count) / drainSeconds
        var jump = 0.0
        for i in 1..<objects.count {
            let a = objects[i - 1].endPosition, b = objects[i].pos
            let gap = max(50, objects[i].time - objects[i - 1].endTime)
            jump += hypot(Double(b.x - a.x), Double(b.y - a.y)) / gap
        }
        jump /= Double(objects.count - 1)
        let s = 0.9 * density + 9 * jump + (difficulty.ar - 5) * 0.25 + (difficulty.od - 5) * 0.12
        return max(0.5, min(10, s * 0.8))
    }

    /// Длина бита и множитель скорости слайдера в момент t.
    func timing(at t: Double) -> (beatLength: Double, sv: Double) {
        var beat = timingPoints.first(where: { $0.uninherited && $0.beatLength > 0 })?.beatLength ?? 500
        var sv = 1.0
        for tp in timingPoints {
            if tp.time > t + 1 { break }
            if tp.uninherited {
                if tp.beatLength > 0 { beat = tp.beatLength }
                sv = 1
            } else if tp.beatLength < 0 {
                sv = max(0.1, min(10, -100 / tp.beatLength))
            }
        }
        return (beat, sv)
    }

    /// Пути, длительности слайдеров, номера и цвета комбо.
    func finalize() {
        timingPoints.sort { $0.time < $1.time }
        objects.sort { $0.time < $1.time }
        var number = 0
        var color = -1
        for (i, o) in objects.enumerated() {
            if o.kind == .slider {
                o.path = SliderPath(type: o.curveType, control: o.controlPoints, pixelLength: o.pixelLength)
                let (beat, sv) = timing(at: o.time)
                let length = o.pixelLength > 0 ? o.pixelLength : (o.path?.length ?? 0)
                o.spanDuration = max(1, length / (difficulty.sliderMultiplier * 100 * sv) * beat)
                o.endTime = o.time + o.spanDuration * Double(max(1, o.slides))
            }
            if i == 0 || o.newCombo || o.kind == .spinner {
                number = 1
                color = (color + 1 + o.comboSkip) % max(1, colors.count)
            } else {
                number += 1
            }
            o.comboNumber = number
            o.colorIndex = max(0, color)
        }
    }
}

enum OsuParseError: LocalizedError {
    case notOsu, unsupportedMode(Int)
    var errorDescription: String? {
        switch self {
        case .notOsu: return "Это не файл карты osu!"
        case .unsupportedMode(let m): return "Режим карты не поддерживается (mode \(m)): играем только в кружки"
        }
    }
}

/// Разбор формата .osu (v3–v14).
enum OsuParser {
    static func parse(url: URL) throws -> Beatmap {
        let data = try Data(contentsOf: url)
        let text = String(data: data, encoding: .utf8) ?? String(decoding: data, as: UTF8.self)
        let map = try parse(text)
        map.fileURL = url
        return map
    }

    static func parse(_ raw: String) throws -> Beatmap {
        let map = Beatmap()
        var text = raw
        if text.hasPrefix("\u{FEFF}") { text.removeFirst() }
        var section = ""
        var sawHeader = false
        var colorPairs: [(Int, RGB)] = []

        for rawLine in text.components(separatedBy: .newlines) {
            let line = rawLine.trimmingCharacters(in: .whitespaces)
            if line.isEmpty || line.hasPrefix("//") { continue }
            if line.hasPrefix("osu file format v") {
                sawHeader = true
                map.formatVersion = Int(line.dropFirst("osu file format v".count)) ?? 14
                continue
            }
            if line.hasPrefix("[") && line.hasSuffix("]") {
                section = String(line.dropFirst().dropLast())
                sawHeader = true
                continue
            }
            switch section {
            case "General", "Metadata", "Difficulty", "Colours":
                guard let colon = line.firstIndex(of: ":") else { continue }
                let key = line[..<colon].trimmingCharacters(in: .whitespaces)
                let value = line[line.index(after: colon)...].trimmingCharacters(in: .whitespaces)
                let num = Double(value)
                switch (section, key) {
                case ("General", "AudioFilename"): map.audioFilename = value
                case ("General", "AudioLeadIn"): map.audioLeadIn = num ?? 0
                case ("General", "PreviewTime"): map.previewTime = num ?? -1
                case ("General", "Mode"): map.mode = Int(value) ?? 0
                case ("Metadata", "Title"): map.title = value
                case ("Metadata", "TitleUnicode"): map.titleUnicode = value
                case ("Metadata", "Artist"): map.artist = value
                case ("Metadata", "ArtistUnicode"): map.artistUnicode = value
                case ("Metadata", "Creator"): map.creator = value
                case ("Metadata", "Version"): map.version = value
                case ("Metadata", "Source"): map.source = value
                case ("Metadata", "Tags"): map.tags = value
                case ("Difficulty", "HPDrainRate"): map.difficulty.hp = num ?? 5
                case ("Difficulty", "CircleSize"): map.difficulty.cs = num ?? 4
                case ("Difficulty", "OverallDifficulty"): map.difficulty.od = num ?? 5
                case ("Difficulty", "ApproachRate"): map.difficulty.ar = num ?? 5
                case ("Difficulty", "SliderMultiplier"): map.difficulty.sliderMultiplier = num ?? 1.4
                case ("Difficulty", "SliderTickRate"): map.difficulty.tickRate = num ?? 1
                case ("Colours", _) where key.hasPrefix("Combo"):
                    let parts = value.split(separator: ",").compactMap { Double($0.trimmingCharacters(in: .whitespaces)) }
                    if parts.count >= 3 {
                        colorPairs.append((Int(key.dropFirst(5)) ?? 99, RGB(r: parts[0] / 255, g: parts[1] / 255, b: parts[2] / 255)))
                    }
                default: break
                }
            case "Events":
                let f = line.split(separator: ",", omittingEmptySubsequences: false).map { String($0).trimmingCharacters(in: .whitespaces) }
                if f.count >= 3, f[0] == "0" || f[0] == "Background" {
                    map.background = f[2].trimmingCharacters(in: CharacterSet(charactersIn: "\""))
                }
            case "TimingPoints":
                let f = line.split(separator: ",").map { String($0).trimmingCharacters(in: .whitespaces) }
                guard f.count >= 2, let time = Double(f[0]), let beat = Double(f[1]) else { continue }
                let meter = f.count > 2 ? Int(f[2]) ?? 4 : 4
                let uninherited = f.count > 6 ? f[6] == "1" : beat > 0
                let effects = f.count > 7 ? Int(f[7]) ?? 0 : 0
                map.timingPoints.append(TimingPoint(time: time, beatLength: beat, meter: meter, uninherited: uninherited, kiai: effects & 1 != 0))
            case "HitObjects":
                if let o = parseObject(line) { map.objects.append(o) }
            default:
                break
            }
        }
        if !sawHeader { throw OsuParseError.notOsu }
        if map.mode != 0 { throw OsuParseError.unsupportedMode(map.mode) }
        if map.difficulty.ar == 5, !text.contains("ApproachRate") { map.difficulty.ar = map.difficulty.od }  // старые карты
        map.comboColors = colorPairs.sorted { $0.0 < $1.0 }.map { $0.1 }
        map.finalize()
        return map
    }

    static func parseObject(_ line: String) -> HitObject? {
        let f = line.split(separator: ",", omittingEmptySubsequences: false).map { String($0) }
        guard f.count >= 4, let x = Double(f[0]), let y = Double(f[1]), let time = Double(f[2]), let type = Int(f[3]) else { return nil }
        let hitSound = f.count > 4 ? Int(f[4]) ?? 0 : 0
        let newCombo = type & 4 != 0
        let skip = (type >> 4) & 7
        let pos = CGPoint(x: x, y: y)
        if type & 1 != 0 {
            return HitObject(kind: .circle, time: time, pos: pos, newCombo: newCombo, comboSkip: skip, hitSound: hitSound)
        }
        if type & 2 != 0, f.count >= 8 {
            let o = HitObject(kind: .slider, time: time, pos: pos, newCombo: newCombo, comboSkip: skip, hitSound: hitSound)
            let curve = f[5].split(separator: "|")
            var points = [pos]
            for (i, part) in curve.enumerated() {
                if i == 0, part.count == 1 { o.curveType = part.first ?? "B"; continue }
                let xy = part.split(separator: ":")
                if xy.count == 2, let px = Double(xy[0]), let py = Double(xy[1]) { points.append(CGPoint(x: px, y: py)) }
            }
            o.controlPoints = points
            o.slides = max(1, Int(f[6]) ?? 1)
            o.pixelLength = Double(f[7]) ?? 0
            return o
        }
        if type & 8 != 0 {
            let end = f.count > 5 ? Double(f[5]) ?? time + 1000 : time + 1000
            return HitObject(kind: .spinner, time: time, pos: CGPoint(x: 256, y: 192), newCombo: true, comboSkip: skip, hitSound: hitSound, endTime: max(time + 1, end))
        }
        return nil  // удержания osu!mania не поддерживаются
    }
}

/// Запись карты в формат .osu v14 (для сгенерированных по треку карт).
enum OsuWriter {
    static func write(_ map: Beatmap) -> String {
        func n(_ v: Double) -> String { v == v.rounded() ? String(Int(v)) : String(format: "%.2f", v) }
        var s = "osu file format v14\n\n[General]\n"
        s += "AudioFilename: \(map.audioFilename)\nAudioLeadIn: \(Int(map.audioLeadIn))\nPreviewTime: \(Int(map.previewTime))\n"
        s += "Countdown: 0\nSampleSet: Soft\nStackLeniency: 0.7\nMode: 0\n\n[Metadata]\n"
        s += "Title:\(map.title)\nTitleUnicode:\(map.titleUnicode)\nArtist:\(map.artist)\nArtistUnicode:\(map.artistUnicode)\n"
        s += "Creator:\(map.creator)\nVersion:\(map.version)\nSource:\(map.source)\nTags:\(map.tags)\n\n[Difficulty]\n"
        let d = map.difficulty
        s += "HPDrainRate:\(n(d.hp))\nCircleSize:\(n(d.cs))\nOverallDifficulty:\(n(d.od))\nApproachRate:\(n(d.ar))\n"
        s += "SliderMultiplier:\(n(d.sliderMultiplier))\nSliderTickRate:\(n(d.tickRate))\n\n[Events]\n"
        if let bg = map.background { s += "0,0,\"\(bg)\",0,0\n" }
        s += "\n[TimingPoints]\n"
        for tp in map.timingPoints {
            s += "\(n(tp.time)),\(String(format: "%.6f", tp.beatLength)),\(tp.meter),2,0,60,\(tp.uninherited ? 1 : 0),\(tp.kiai ? 1 : 0)\n"
        }
        s += "\n[HitObjects]\n"
        for o in map.objects {
            let x = Int(o.pos.x.rounded()), y = Int(o.pos.y.rounded())
            let combo = o.newCombo ? 4 : 0
            switch o.kind {
            case .circle:
                s += "\(x),\(y),\(Int(o.time)),\(1 | combo),\(o.hitSound),0:0:0:0:\n"
            case .slider:
                let pts = o.controlPoints.dropFirst().map { "\(Int($0.x.rounded())):\(Int($0.y.rounded()))" }.joined(separator: "|")
                s += "\(x),\(y),\(Int(o.time)),\(2 | combo),\(o.hitSound),\(o.curveType)|\(pts),\(o.slides),\(n(o.pixelLength))\n"
            case .spinner:
                s += "256,192,\(Int(o.time)),\(8 | 4),\(o.hitSound),\(Int(o.endTime)),0:0:0:0:\n"
            }
        }
        return s
    }
}
