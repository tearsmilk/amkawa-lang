import AppKit
import AVFoundation

/// `TnQkoMusically --selftest`: проверка без участия человека (CI).
enum SelfTest {
    static let sample = """
    osu file format v14

    [General]
    AudioFilename: audio.wav
    AudioLeadIn: 0
    PreviewTime: 2000
    Mode: 0

    [Metadata]
    Title:Self Test
    TitleUnicode:Самопроверка
    Artist:TnQko
    Creator:tearsmilk
    Version:Тест

    [Difficulty]
    HPDrainRate:5
    CircleSize:4
    OverallDifficulty:6
    ApproachRate:8
    SliderMultiplier:1.4
    SliderTickRate:1

    [Events]
    0,0,"bg.png",0,0

    [TimingPoints]
    2000,500,4,2,0,60,1,0
    6000,-50,4,2,0,60,0,1

    [Colours]
    Combo1 : 255,128,64
    Combo2 : 64,128,255

    [HitObjects]
    100,100,2000,5,0,0:0:0:0:
    200,100,2500,1,0,0:0:0:0:
    200,200,3000,2,0,L|300:200,1,100
    300,300,4000,6,0,P|350:250|400:300,2,120
    100,300,5500,2,0,B|150:250|200:300|200:300|250:350,1,180
    256,192,6000,12,0,8000,0:0:0:0:
    400,100,8500,1,0,0:0:0:0:
    """

    static func run() -> Int32 {
        var failures = 0
        func check(_ ok: Bool, _ name: String) {
            print(ok ? "ok    \(name)" : "FAIL  \(name)")
            if !ok { failures += 1 }
        }
        _ = NSApplication.shared
        NSApp.setActivationPolicy(.accessory)
        let fm = FileManager.default
        let tmp = fm.temporaryDirectory.appendingPathComponent("tnqkomusic-selftest-\(getpid())", isDirectory: true)
        try? fm.createDirectory(at: tmp, withIntermediateDirectories: true)
        defer { try? fm.removeItem(at: tmp) }

        // разбор .osu
        var map: Beatmap?
        do { map = try OsuParser.parse(sample) } catch { print("parse error: \(error)") }
        check(map != nil, "разбор .osu")
        if let m = map {
            let c = m.counts
            check(c.circles == 3 && c.sliders == 3 && c.spinners == 1, "типы объектов (\(c.circles)/\(c.sliders)/\(c.spinners))")
            check(m.displayTitle == "Самопроверка" && m.version == "Тест" && m.background == "bg.png", "метаданные и фон")
            check(m.comboColors.count == 2 && abs(m.bpm - 120) < 0.01, "цвета и BPM")
            let linear = m.objects[2]
            check(abs((linear.path?.length ?? 0) - 100) < 0.5 && abs(linear.duration - 357.14) < 1, "линейный слайдер: длина и длительность")
            let arc = m.objects[3]
            check(abs((arc.path?.length ?? 0) - 120) < 0.5 && arc.slides == 2 && abs(arc.endTime - (4000 + 2 * 120 / 140 * 500)) < 1, "дуга с повтором")
            let mid = arc.sliderPosition(at: arc.time + arc.spanDuration), back = arc.sliderPosition(at: arc.endTime)
            check(hypot(back.x - arc.pos.x, back.y - arc.pos.y) < 1 && hypot(mid.x - arc.pos.x, mid.y - arc.pos.y) > 50, "повтор возвращает шар")
            check(abs((m.objects[4].path?.length ?? 0) - 180) < 0.5, "Безье с красным узлом")
            check(m.objects[0].comboNumber == 1 && m.objects[1].comboNumber == 2 && m.objects[3].comboNumber == 1, "номера комбо")
            check(abs(m.difficulty.preempt - 750) < 0.01 && abs(m.difficulty.window300 - 44) < 0.01, "AR / OD")
            let reparsed = try? OsuParser.parse(OsuWriter.write(m))
            check(reparsed?.objects.count == m.objects.count && abs((reparsed?.endTime ?? 0) - m.endTime) < 2, "запись и повторное чтение .osu")

            let s = GameSession(map: m)
            GameSession.autoplay(s)
            check(s.counts[.miss] == 0 && s.accuracy > 0.99 && (s.grade == "SS" || s.grade == "S"), "идеальная игра: \(s.grade) \(String(format: "%.2f", s.accuracy * 100))%")
            check(s.maxCombo >= m.objects.count, "комбо \(s.maxCombo)")
            let lazy = GameSession(map: (try? OsuParser.parse(sample)) ?? m)
            var t = 0.0
            while t < 9000 { lazy.update(t: t, cursor: .zero, held: false); t += 16 }
            check(lazy.failed && lazy.score == 0, "без нажатий — провал")
        }
        check((try? OsuParser.parse("hello")) == nil, "не-osu отклоняется")
        check((try? OsuParser.parse("osu file format v14\n[General]\nMode: 3\n")) == nil, "mania отклоняется")

        // свой трек: 120 BPM, 20 секунд
        let wav = tmp.appendingPathComponent("Test Artist - Click Song.wav")
        check(writeClickTrack(wav, bpm: 120, seconds: 20), "тестовый трек записан")
        if let a = try? BeatGen.analyze(wav) {
            check(abs(a.bpm - 120) < 1.5, String(format: "темп найден: %.2f BPM", a.bpm))
            let phase = a.offsetMs.truncatingRemainder(dividingBy: 500)
            check(min(phase, 500 - phase) < 25, String(format: "фаза бита: %.0f мс", a.offsetMs))
            for level in Level.allCases {
                let g = BeatGen.generate(a, level: level, audioFilename: "a.wav", title: "T", artist: "A", seed: 1)
                let inField = g.objects.allSatisfy { o in
                    let pts = [o.pos, o.endPosition]
                    return pts.allSatisfy { $0.x >= 0 && $0.x <= 512 && $0.y >= 0 && $0.y <= 384 }
                }
                check(g.objects.count > 8 && inField, "генерация «\(level.title)»: \(g.objects.count) объектов")
                let s = GameSession(map: g)
                GameSession.autoplay(s)
                check(s.counts[.miss] == 0 && s.accuracy > 0.99, "сгенерированная «\(level.title)» проходима")
            }
        } else {
            check(false, "анализ трека")
        }

        // библиотека
        let lib = Library(root: tmp.appendingPathComponent("lib", isDirectory: true))
        do {
            let folder = try lib.importAudio(wav)
            lib.scan()
            check(lib.maps.count == 3, "свой трек → 3 сложности")
            check(lib.maps.first?.displayArtist == "Test Artist" && lib.maps.first?.displayTitle == "Click Song", "название из имени файла")
            // .osz из этой папки
            let osz = tmp.appendingPathComponent("pack.osz")
            let zip = Process()
            zip.executableURL = URL(fileURLWithPath: "/usr/bin/ditto")
            zip.arguments = ["-c", "-k", folder.path, osz.path]
            try zip.run()
            zip.waitUntilExit()
            try lib.importOsz(osz)
            lib.scan()
            check(lib.maps.count == 6, "импорт .osz")
            check(lib.maps.allSatisfy { $0.audioURL.map { fm.fileExists(atPath: $0.path) } ?? false }, "аудио рядом с картами")
            let clock = try MusicClock(url: lib.maps[0].audioURL!)
            check(clock.duration > 19, "музыка открывается")
        } catch {
            check(false, "библиотека: \(error.localizedDescription)")
        }
        let badOsz = tmp.appendingPathComponent("bad.osz")
        try? "not a zip".write(to: badOsz, atomically: true, encoding: .utf8)
        check((try? lib.importOsz(badOsz)) == nil, "битый .osz отклоняется")

        // рекорды
        let suite = "com.tearsmilk.tnqkomusically.selftest.\(getpid())"
        if let d = UserDefaults(suiteName: suite) {
            let st = Settings(defaults: d)
            check(st.submit("k", .init(score: 100, accuracy: 0.9, combo: 5, grade: "B")) && !st.submit("k", .init(score: 50, accuracy: 1, combo: 1, grade: "SS")) && st.best("k")?.score == 100, "рекорды")
            d.removePersistentDomain(forName: suite)
        }

        // отрисовка
        if let m = lib.maps.last {
            let g = GameView(map: m, clock: nil, sounds: nil, settings: Settings(defaults: UserDefaults(suiteName: suite) ?? .standard))
            g.frame = NSRect(x: 0, y: 0, width: 1280, height: 800)
            var drew = true
            for t in stride(from: m.firstTime - 500, to: m.firstTime + 4000, by: 250) {
                g.manualTime = t
                g.session.update(t: t, cursor: CGPoint(x: 256, y: 192), held: t.truncatingRemainder(dividingBy: 500) < 250)
                guard let rep = g.bitmapImageRepForCachingDisplay(in: g.bounds) else { drew = false; break }
                g.cacheDisplay(in: g.bounds, to: rep)
            }
            check(drew, "игровой экран рисуется")
            let ss = SongSelectView(library: lib, settings: Settings(defaults: UserDefaults(suiteName: suite) ?? .standard))
            ss.frame = NSRect(x: 0, y: 0, width: 1280, height: 800)
            ss.layoutSubtreeIfNeeded()
            check(ss.mapCount == 6, "список песен")
            ss.stopPreview()
            let r = ResultsView(session: g.session, isRecord: true, onRetry: {}, onBack: {})
            r.frame = NSRect(x: 0, y: 0, width: 1280, height: 800)
            r.layoutSubtreeIfNeeded()
            check(true, "экран итогов")
        }
        _ = HitSounds()

        if Bundle.main.bundleURL.pathExtension == "app" {
            check(Bundle.main.url(forResource: "AppIcon", withExtension: "icns") != nil, "иконка в бандле")
        }
        print(failures == 0 ? "selftest: OK" : "selftest: \(failures) FAIL")
        return failures == 0 ? 0 : 1
    }

    /// Щелчки на каждом бите (сильная доля громче) + тихий гул, чтобы трек не считался тишиной.
    static func writeClickTrack(_ url: URL, bpm: Double, seconds: Double) -> Bool {
        let sr = 44100.0
        guard let format = AVAudioFormat(standardFormatWithSampleRate: sr, channels: 1),
              let file = try? AVAudioFile(forWriting: url, settings: [
                  AVFormatIDKey: kAudioFormatLinearPCM, AVSampleRateKey: sr, AVNumberOfChannelsKey: 1,
                  AVLinearPCMBitDepthKey: 16, AVLinearPCMIsFloatKey: false,
              ]) else { return false }
        let frames = AVAudioFrameCount(sr * seconds)
        guard let buf = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: frames), let d = buf.floatChannelData?[0] else { return false }
        buf.frameLength = frames
        let beat = 60 / bpm
        var rng = SplitMix(seed: 42)
        for i in 0..<Int(frames) {
            let t = Double(i) / sr
            let k = Int(t / beat)
            let since = t - Double(k) * beat
            let accent = k % 4 == 0 ? 1.0 : 0.7
            var s = 0.15 * sin(2 * .pi * 110 * t)
            if since < 0.03 {
                s += accent * (rng.next(in: -1..<1) * 0.6 + sin(2 * .pi * 1500 * since) * 0.4) * exp(-since * 120)
            }
            d[i] = Float(max(-1, min(1, s)))
        }
        do { try file.write(from: buf) } catch { return false }
        return true
    }
}
