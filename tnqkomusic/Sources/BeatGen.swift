import AVFoundation
import CoreGraphics
import Foundation

/// Анализ трека: громкость, огибающая атак, темп и фаза бита.
struct AudioAnalysis {
    let duration: Double        // сек
    let frameRate: Double       // кадров огибающей в секунду
    let onset: [Float]          // сила атаки по кадрам, 0…1
    let loudness: [Float]       // сглаженная громкость, 0…1
    let bpm: Double
    let offsetMs: Double        // время первого бита

    var beatMs: Double { 60000 / bpm }

    func onset(atMs t: Double) -> Float {
        guard !onset.isEmpty else { return 0 }
        let i = max(0, min(onset.count - 1, Int((t / 1000 * frameRate).rounded())))
        var m: Float = 0
        for j in max(0, i - 2)...min(onset.count - 1, i + 2) { m = max(m, onset[j]) }
        return m
    }

    func loudness(atMs t: Double) -> Float {
        let i = Int(t / 1000 * frameRate)
        guard !loudness.isEmpty else { return 0 }
        return loudness[max(0, min(loudness.count - 1, i))]
    }
}

enum BeatGenError: LocalizedError {
    case tooShort, silent
    var errorDescription: String? {
        switch self {
        case .tooShort: return "Трек слишком короткий (нужно хотя бы 10 секунд)"
        case .silent: return "В треке не нашлось ритма"
        }
    }
}

enum Level: Int, CaseIterable {
    case easy, normal, hard

    var title: String {
        switch self {
        case .easy: return "Лёгкая"
        case .normal: return "Нормальная"
        case .hard: return "Сложная"
        }
    }

    var difficulty: Difficulty {
        switch self {
        case .easy: return Difficulty(hp: 3, cs: 3, od: 3, ar: 4.5, sliderMultiplier: 1.2, tickRate: 1)
        case .normal: return Difficulty(hp: 5, cs: 4, od: 5.5, ar: 7, sliderMultiplier: 1.4, tickRate: 1)
        case .hard: return Difficulty(hp: 6, cs: 4.2, od: 7.5, ar: 8.8, sliderMultiplier: 1.7, tickRate: 1)
        }
    }

    /// osu!-пикселей на один бит промежутка.
    var spacing: Double { [70, 95, 125][rawValue] }
    var turn: Double { [0.6, 0.9, 1.4][rawValue] }
    var sliderChance: Double { [0.35, 0.3, 0.25][rawValue] }
}

enum BeatGen {
    static let hopBase = 512

    static func analyze(_ url: URL) throws -> AudioAnalysis {
        let file = try AVAudioFile(forReading: url)
        let format = file.processingFormat
        let sr = format.sampleRate
        let channels = Int(format.channelCount)
        let hop = max(128, Int((sr / 44100 * Double(hopBase)).rounded()))
        let chunk: AVAudioFrameCount = 1 << 16
        guard let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: chunk) else { throw BeatGenError.silent }

        var energy: [Float] = []
        var hfEnergy: [Float] = []
        var accE: Float = 0, accH: Float = 0
        var count = 0
        var prev: Float = 0
        while file.framePosition < file.length {
            try file.read(into: buffer, frameCount: chunk)
            let n = Int(buffer.frameLength)
            if n == 0 { break }
            guard let data = buffer.floatChannelData else { break }
            for i in 0..<n {
                var s: Float = 0
                for c in 0..<channels { s += data[c][i] }
                s /= Float(channels)
                let d = s - prev
                prev = s
                accE += s * s
                accH += d * d
                count += 1
                if count == hop {
                    energy.append(sqrtf(accE / Float(hop)))
                    hfEnergy.append(sqrtf(accH / Float(hop)))
                    accE = 0
                    accH = 0
                    count = 0
                }
            }
        }
        let duration = Double(file.length) / sr
        let fr = sr / Double(hop)
        guard duration >= 10, energy.count > Int(fr * 5) else { throw BeatGenError.tooShort }

        // огибающая атак: рост громкости (с упором на верха) минус локальное среднее
        var raw = [Float](repeating: 0, count: energy.count)
        for i in 1..<energy.count {
            raw[i] = max(0, hfEnergy[i] - hfEnergy[i - 1]) * 2 + max(0, energy[i] - energy[i - 1])
        }
        let win = max(4, Int(fr * 0.25))
        var onset = [Float](repeating: 0, count: raw.count)
        var sum: Float = 0
        for i in 0..<raw.count {
            sum += raw[i]
            if i >= 2 * win { sum -= raw[i - 2 * win] }
            let mean = sum / Float(min(i + 1, 2 * win))
            onset[max(0, i - win)] = max(0, raw[max(0, i - win)] - mean)
        }
        let peak = percentile(onset, 0.98)
        guard peak > 0 else { throw BeatGenError.silent }
        for i in 0..<onset.count { onset[i] = min(1, onset[i] / peak) }

        // сглаженная громкость 0…1
        var loud = [Float](repeating: 0, count: energy.count)
        let lw = max(2, Int(fr * 0.2))
        var ls: Float = 0
        for i in 0..<energy.count {
            ls += energy[i]
            if i >= lw { ls -= energy[i - lw] }
            loud[i] = ls / Float(min(i + 1, lw))
        }
        let lmax = percentile(loud, 0.99)
        if lmax > 0 { for i in 0..<loud.count { loud[i] = min(1, loud[i] / lmax) } }

        let (period, phase) = tempo(onset, fr: fr)
        let bpm = 60 * fr / period
        let offset = phase / fr * 1000
        return AudioAnalysis(duration: duration, frameRate: fr, onset: onset, loudness: loud, bpm: bpm, offsetMs: offset)
    }

    static func percentile(_ v: [Float], _ p: Double) -> Float {
        guard !v.isEmpty else { return 0 }
        let s = v.sorted()
        return s[min(s.count - 1, Int(Double(s.count - 1) * p))]
    }

    /// Период (в кадрах огибающей) и фаза бита: автокорреляция с предпочтением ~120 BPM, затем уточнение «гребёнкой».
    static func tempo(_ o: [Float], fr: Double) -> (period: Double, phase: Double) {
        let minLag = Int(60 * fr / 200), maxLag = Int(60 * fr / 70) + 1
        let n = o.count
        var best = (lag: Double(minLag), score: -1.0)
        var ac = [Double](repeating: 0, count: maxLag + 2)
        for lag in minLag...(maxLag + 1) where lag < n {
            var s = 0.0
            var i = 0
            while i + lag < n { s += Double(o[i]) * Double(o[i + lag]); i += 1 }
            ac[lag] = s / Double(n - lag)
        }
        for lag in minLag...maxLag where lag < n {
            let bpm = 60 * fr / Double(lag)
            let w = exp(-0.5 * pow(log2(bpm / 125) / 0.7, 2))
            let score = ac[lag] * w
            if score > best.score { best = (Double(lag), score) }
        }
        // параболическая интерполяция
        let l = Int(best.lag)
        if l > minLag, l < maxLag {
            let a = ac[l - 1], b = ac[l], c = ac[l + 1]
            let den = a - 2 * b + c
            if abs(den) > 1e-12 { best.lag = Double(l) + 0.5 * (a - c) / den }
        }
        // уточнение периода и фазы по сумме атак на сетке битов
        var bestP = best.lag, bestPhase = 0.0, bestSum = -1.0
        var p = best.lag * 0.985
        while p <= best.lag * 1.015 {
            var ph = 0.0
            while ph < p {
                var s = 0.0
                var t = ph
                while t < Double(n - 1) {
                    let i = Int(t.rounded())
                    s += Double(max(o[max(0, i - 1)], o[i], o[min(n - 1, i + 1)]))
                    t += p
                }
                if s > bestSum { bestSum = s; bestP = p; bestPhase = ph }
                ph += 1
            }
            p += best.lag * 0.0025
        }
        return (bestP, bestPhase)
    }

    /// Карта по анализу: кружки на битах (и полубитах на сложной), слайдеры, плавная траектория по полю.
    static func generate(_ a: AudioAnalysis, level: Level, audioFilename: String, title: String, artist: String, seed: UInt64) -> Beatmap {
        let map = Beatmap()
        map.audioFilename = audioFilename
        map.title = title
        map.titleUnicode = title
        map.artist = artist
        map.artistUnicode = artist
        map.creator = "TnQkoMusically"
        map.version = level.title
        map.tags = "tnqko generated"
        map.previewTime = (a.duration * 0.4 * 1000).rounded()
        map.difficulty = level.difficulty
        let beat = a.beatMs
        map.timingPoints = [TimingPoint(time: a.offsetMs.rounded(), beatLength: beat, meter: 4, uninherited: true, kiai: false)]

        var rng = SplitMix(seed: seed &+ UInt64(level.rawValue) &* 7919)
        // кандидаты: (время, номер бита в долях)
        var times: [(t: Double, beats: Double)] = []
        let total = Int((a.duration * 1000 - a.offsetMs - 800) / beat)
        for k in 0..<max(0, total) {
            let t = a.offsetMs + Double(k) * beat
            if t < 1500 || a.loudness(atMs: t) < 0.12 { continue }
            let strong = a.onset(atMs: t)
            switch level {
            case .easy:
                if k % 2 == 0 || strong > 0.85 { times.append((t, Double(k))) }
            case .normal:
                if strong > 0.08 || k % 2 == 0 { times.append((t, Double(k))) }
            case .hard:
                times.append((t, Double(k)))
                let half = t + beat / 2
                if a.onset(atMs: half) > 0.45 && a.loudness(atMs: half) > 0.2 { times.append((half, Double(k) + 0.5)) }
            }
        }

        let r = map.difficulty.radius
        let minX = r + 12, maxX = 512 - r - 12, minY = r + 12, maxY = 384 - r - 12
        var pos = CGPoint(x: 256, y: 192)
        var angle = rng.next(in: 0..<(2 * .pi))
        var lastComboBar = -1
        var i = 0
        while i < times.count {
            let (t, b) = times[i]
            let gapBeats = i + 1 < times.count ? times[i + 1].beats - b : 4
            let bar = Int(b) / 4
            let newCombo = bar != lastComboBar || (i > 0 && b - times[i - 1].beats >= 2)
            if newCombo { lastComboBar = bar }

            if i > 0 {
                let prevGap = b - times[i - 1].beats
                angle += rng.next(in: -level.turn..<level.turn)
                let dist = min(220, level.spacing * max(0.5, min(3, prevGap)))
                pos = step(pos, angle: &angle, dist: dist, minX: minX, maxX: maxX, minY: minY, maxY: maxY)
            }

            let makeSlider = gapBeats >= 2 && rng.next(in: 0..<1) < level.sliderChance
            if makeSlider {
                let spanBeats = gapBeats >= 3 && rng.next(in: 0..<1) < 0.3 ? 1.0 : min(2, gapBeats - 1)
                let slides = spanBeats <= 1 && rng.next(in: 0..<1) < 0.25 ? 2 : 1
                let beatsPerSpan = spanBeats / Double(slides)
                let length = beatsPerSpan * 100 * map.difficulty.sliderMultiplier
                var dir = angle
                var end = CGPoint(x: pos.x + CGFloat(cos(dir) * length), y: pos.y + CGFloat(sin(dir) * length))
                for _ in 0..<8 where !(minX...maxX).contains(Double(end.x)) || !(minY...maxY).contains(Double(end.y)) {
                    dir += .pi / 4
                    end = CGPoint(x: pos.x + CGFloat(cos(dir) * length), y: pos.y + CGFloat(sin(dir) * length))
                }
                end = CGPoint(x: max(minX, min(maxX, Double(end.x))), y: max(minY, min(maxY, Double(end.y))))
                let o = HitObject(kind: .slider, time: t.rounded(), pos: pos, newCombo: newCombo || i == 0)
                let bend = rng.next(in: -0.35..<0.35)
                if abs(bend) > 0.12 {
                    let mid = CGPoint(x: (pos.x + end.x) / 2 - CGFloat(sin(dir) * length * bend), y: (pos.y + end.y) / 2 + CGFloat(cos(dir) * length * bend))
                    o.curveType = "P"
                    o.controlPoints = [pos, mid, end]
                } else {
                    o.curveType = "L"
                    o.controlPoints = [pos, end]
                }
                o.slides = slides
                o.pixelLength = length
                map.objects.append(o)
                angle = dir
                pos = slides % 2 == 0 ? pos : end
                // пропускаем кандидатов, которые попали внутрь слайдера
                let endBeat = b + spanBeats
                i += 1
                while i < times.count && times[i].beats < endBeat + 0.75 { i += 1 }
                continue
            }
            map.objects.append(HitObject(kind: .circle, time: t.rounded(), pos: pos, newCombo: newCombo || i == 0))
            i += 1
        }
        map.finalize()
        return map
    }

    private static func step(_ p: CGPoint, angle: inout Double, dist: Double, minX: Double, maxX: Double, minY: Double, maxY: Double) -> CGPoint {
        var x = Double(p.x) + cos(angle) * dist
        var y = Double(p.y) + sin(angle) * dist
        if x < minX || x > maxX { angle = .pi - angle; x = Double(p.x) + cos(angle) * dist }
        if y < minY || y > maxY { angle = -angle; y = Double(p.y) + sin(angle) * dist }
        return CGPoint(x: max(minX, min(maxX, x)), y: max(minY, min(maxY, y)))
    }

    /// Название и исполнитель: из тегов файла, иначе из имени «Исполнитель - Название».
    static func metadata(_ url: URL) -> (title: String, artist: String) {
        let asset = AVURLAsset(url: url)
        var title = "", artist = ""
        for item in asset.commonMetadata {
            if item.commonKey == .commonKeyTitle, let v = item.stringValue { title = v }
            if item.commonKey == .commonKeyArtist, let v = item.stringValue { artist = v }
        }
        let name = url.deletingPathExtension().lastPathComponent
        if title.isEmpty || artist.isEmpty {
            let parts = name.components(separatedBy: " - ")
            if parts.count >= 2 {
                if artist.isEmpty { artist = parts[0].trimmingCharacters(in: .whitespaces) }
                if title.isEmpty { title = parts.dropFirst().joined(separator: " - ").trimmingCharacters(in: .whitespaces) }
            }
        }
        return (title.isEmpty ? name : title, artist.isEmpty ? "Неизвестный исполнитель" : artist)
    }
}

/// Детерминированный ГПСЧ: одна и та же песня — одна и та же карта.
struct SplitMix {
    private var state: UInt64
    init(seed: UInt64) { state = seed }

    mutating func nextUInt() -> UInt64 {
        state &+= 0x9E3779B97F4A7C15
        var z = state
        z = (z ^ (z >> 30)) &* 0xBF58476D1CE4E5B9
        z = (z ^ (z >> 27)) &* 0x94D049BB133111EB
        return z ^ (z >> 31)
    }

    mutating func next(in range: Range<Double>) -> Double {
        range.lowerBound + Double(nextUInt() >> 11) / Double(1 << 53) * (range.upperBound - range.lowerBound)
    }
}
