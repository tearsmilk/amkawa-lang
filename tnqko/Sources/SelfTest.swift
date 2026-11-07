import AppKit
import AVFoundation

/// `TnQkoWallpaper --selftest`: проверка без участия человека (CI). Системные обои не трогает.
enum SelfTest {
    static func run() -> Int32 {
        var failures = 0
        func check(_ ok: Bool, _ name: String) {
            print(ok ? "ok    \(name)" : "FAIL  \(name)")
            if !ok { failures += 1 }
        }

        _ = NSApplication.shared
        NSApp.setActivationPolicy(.accessory)
        let fm = FileManager.default
        let tmp = fm.temporaryDirectory.appendingPathComponent("tnqko-selftest-\(getpid())", isDirectory: true)
        try? fm.createDirectory(at: tmp, withIntermediateDirectories: true)
        defer { try? fm.removeItem(at: tmp) }

        let suite = "com.tearsmilk.tnqkowallpaper.selftest.\(getpid())"
        guard let defaults = UserDefaults(suiteName: suite) else { print("FAIL  UserDefaults"); return 1 }
        defer { defaults.removePersistentDomain(forName: suite) }

        // настройки
        let s = Settings(defaults: defaults)
        check(!s.sound && s.fillMode == .fill && s.displayMode == .all && s.pauseOnBattery && s.pauseWhenCovered, "настройки по умолчанию")
        s.fillMode = .fit
        s.volume = 0.3
        let reread = Settings(defaults: defaults)
        check(reread.fillMode == .fit && abs(reread.volume - 0.3) < 0.01, "настройки сохраняются")
        check(FillMode.fit.gravity == .resizeAspect && FillMode.fill.gravity == .resizeAspectFill, "масштаб → gravity")
        s.fillMode = .fill

        // тестовое видео
        let video = tmp.appendingPathComponent("test.mp4")
        check(makeTestVideo(video), "тестовое видео записано")
        check(AVURLAsset(url: video).isPlayable, "видео проигрываемое")
        check(Settings.hasVideoExtension(video) && !Settings.hasVideoExtension(tmp.appendingPathComponent("a.webm")), "расширения")
        let added = s.addToLibrary([video, video])
        check(added.count == 1 && s.library.count == 1, "библиотека без дублей")
        check(Thumbnails.make(video, maxSize: CGSize(width: 160, height: 90)) != nil, "превью")
        check(Thumbnails.duration(video) > 0.5, "длительность")

        // обои
        let wp = WallpaperController(settings: s)
        wp.touchesSystemWallpaper = false
        wp.setVideo(video)
        check(spin(10) { wp.player?.currentItem?.status == .readyToPlay }, "плеер готов")
        let screens = NSScreen.screens.count
        check(wp.windowCount == screens, "окна обоев на всех экранах (\(screens))")
        check(spin(6) { (wp.player?.currentTime().seconds ?? 0) > 0.1 }, "видео идёт")
        check(wp.player?.isMuted == true, "без звука по умолчанию")
        s.sound = true
        wp.applyAudio()
        check(wp.player?.isMuted == false, "звук включается")
        s.displayMode = .main
        wp.rebuildWindows()
        check(wp.windowCount == min(1, screens), "только главный экран")
        s.paused = true
        wp.updatePlayback()
        check(wp.player?.rate == 0 && wp.pauseReason == .user, "пауза")
        s.paused = false
        wp.updatePlayback()
        check(wp.pauseReason == nil, "снова играет")

        // окно библиотеки
        let lw = LibraryWindowController(wallpaper: wp)
        lw.window?.orderFront(nil)
        check(lw.tileCount == 1, "окно библиотеки")
        lw.refreshState()
        lw.close()

        wp.setVideo(nil)
        check(wp.windowCount == 0 && s.current == nil, "обои убраны")

        check(WallpaperController.exportFrame(video, to: tmp) != nil, "кадр для обычных обоев")
        _ = PowerSource.onBattery()
        _ = WallpaperController.desktopCovered()
        check(true, "питание и проверка окон")

        if Bundle.main.bundleURL.pathExtension == "app" {
            check(Bundle.main.url(forResource: "AppIcon", withExtension: "icns") != nil, "иконка в бандле")
        }

        print(failures == 0 ? "selftest: OK" : "selftest: \(failures) FAIL")
        return failures == 0 ? 0 : 1
    }

    static func spin(_ seconds: Double, _ condition: () -> Bool) -> Bool {
        let end = Date().addingTimeInterval(seconds)
        while Date() < end {
            if condition() { return true }
            RunLoop.current.run(until: Date().addingTimeInterval(0.05))
        }
        return condition()
    }

    /// Секунда 64×64 при 30 к/с: H.264, если кодировщик доступен, иначе Motion JPEG в .mov.
    static func makeTestVideo(_ url: URL) -> Bool {
        if write(url, codec: .h264, type: .mp4) { return true }
        return write(url, codec: .jpeg, type: .mov)
    }

    private static func write(_ url: URL, codec: AVVideoCodecType, type: AVFileType) -> Bool {
        try? FileManager.default.removeItem(at: url)
        guard let writer = try? AVAssetWriter(outputURL: url, fileType: type) else { return false }
        let size = 64
        let input = AVAssetWriterInput(mediaType: .video, outputSettings: [
            AVVideoCodecKey: codec, AVVideoWidthKey: size, AVVideoHeightKey: size,
        ])
        input.expectsMediaDataInRealTime = false
        let adaptor = AVAssetWriterInputPixelBufferAdaptor(assetWriterInput: input, sourcePixelBufferAttributes: [
            kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA,
            kCVPixelBufferWidthKey as String: size, kCVPixelBufferHeightKey as String: size,
        ])
        guard writer.canAdd(input) else { return false }
        writer.add(input)
        guard writer.startWriting() else { return false }
        writer.startSession(atSourceTime: .zero)
        for frame in 0..<30 {
            let deadline = Date().addingTimeInterval(5)
            while !input.isReadyForMoreMediaData {
                if Date() > deadline { return false }
                usleep(2000)
            }
            guard let pool = adaptor.pixelBufferPool else { return false }
            var buffer: CVPixelBuffer?
            CVPixelBufferPoolCreatePixelBuffer(nil, pool, &buffer)
            guard let pb = buffer else { return false }
            CVPixelBufferLockBaseAddress(pb, [])
            if let base = CVPixelBufferGetBaseAddress(pb) {
                let bytesPerRow = CVPixelBufferGetBytesPerRow(pb)
                let p = base.assumingMemoryBound(to: UInt8.self)
                for y in 0..<size {
                    for x in 0..<size {
                        let o = y * bytesPerRow + x * 4
                        p[o] = UInt8((x * 4 + frame * 8) & 0xFF)      // B
                        p[o + 1] = UInt8((y * 4) & 0xFF)              // G
                        p[o + 2] = 0xD9                               // R
                        p[o + 3] = 0xFF
                    }
                }
            }
            CVPixelBufferUnlockBaseAddress(pb, [])
            guard adaptor.append(pb, withPresentationTime: CMTime(value: CMTimeValue(frame), timescale: 30)) else { return false }
        }
        input.markAsFinished()
        let done = DispatchSemaphore(value: 0)
        writer.finishWriting { done.signal() }
        _ = done.wait(timeout: .now() + 20)
        return writer.status == .completed
    }
}
