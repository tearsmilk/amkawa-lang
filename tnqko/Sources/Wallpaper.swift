import AppKit
import AVFoundation

/// Окно на уровне рабочего стола: под иконками, на всех Spaces, не ловит мышь.
final class WallpaperWindow: NSWindow {
    init(screen: NSScreen) {
        super.init(contentRect: screen.frame, styleMask: [.borderless], backing: .buffered, defer: false)
        level = NSWindow.Level(rawValue: Int(CGWindowLevelForKey(.desktopWindow)))
        collectionBehavior = [.canJoinAllSpaces, .stationary, .ignoresCycle, .fullScreenNone]
        ignoresMouseEvents = true
        isOpaque = true
        hasShadow = false
        backgroundColor = .black
        isReleasedWhenClosed = false
        animationBehavior = .none
        setFrame(screen.frame, display: false)
    }

    override var canBecomeKey: Bool { false }
    override var canBecomeMain: Bool { false }
}

/// Проигрывает выбранное видео по кругу на окнах рабочего стола; один плеер на все экраны (звук не двоится).
final class WallpaperController {
    enum PauseReason: String {
        case user = "На паузе"
        case sleep = "Пауза: экран спит"
        case battery = "Пауза: работа от батареи"
        case covered = "Пауза: окно на весь экран"
    }

    let settings: Settings
    /// Ставить ли кадр обычными обоями (самопроверка выключает, чтобы не трогать систему).
    var touchesSystemWallpaper = true
    var onStateChange: (() -> Void)?

    private(set) var player: AVQueuePlayer?
    private var looper: AVPlayerLooper?
    private var screens: [(window: WallpaperWindow, layer: AVPlayerLayer)] = []
    private var observers: [(NotificationCenter, NSObjectProtocol)] = []
    private var timer: Timer?
    private var screensAsleep = false
    private(set) var onBattery = false
    private(set) var covered = false

    init(settings: Settings) {
        self.settings = settings
    }

    var windowCount: Int { screens.count }
    var currentURL: URL? { player == nil ? nil : settings.current }

    func start() {
        let nc = NotificationCenter.default
        observers.append((nc, nc.addObserver(forName: NSApplication.didChangeScreenParametersNotification, object: nil, queue: .main) { [weak self] _ in
            self?.rebuildWindows()
        }))
        let wnc = NSWorkspace.shared.notificationCenter
        let sleepEvents: [(Notification.Name, Bool)] = [
            (NSWorkspace.screensDidSleepNotification, true), (NSWorkspace.screensDidWakeNotification, false),
            (NSWorkspace.sessionDidResignActiveNotification, true), (NSWorkspace.sessionDidBecomeActiveNotification, false),
        ]
        for (name, asleep) in sleepEvents {
            observers.append((wnc, wnc.addObserver(forName: name, object: nil, queue: .main) { [weak self] _ in
                self?.screensAsleep = asleep
                self?.updatePlayback()
            }))
        }
        timer = Timer.scheduledTimer(withTimeInterval: 2, repeats: true) { [weak self] _ in self?.poll() }
        poll()
        if let url = settings.current, FileManager.default.fileExists(atPath: url.path) {
            setVideo(url)
        }
    }

    // MARK: видео

    func setVideo(_ url: URL?) {
        looper?.disableLooping()
        looper = nil
        player?.pause()
        player = nil
        settings.current = url
        guard let url = url else {
            tearDownWindows()
            onStateChange?()
            return
        }
        let p = AVQueuePlayer()
        p.preventsDisplaySleepDuringVideoPlayback = false  // обои не должны мешать дисплею засыпать
        looper = AVPlayerLooper(player: p, templateItem: AVPlayerItem(url: url))
        player = p
        applyAudio()
        rebuildWindows()
        updatePlayback()
        if touchesSystemWallpaper && settings.staticWallpaper { setStaticWallpaper(from: url) }
        onStateChange?()
    }

    /// Убирает живые обои и возвращает прежнюю картинку рабочего стола.
    func clear() {
        setVideo(nil)
        guard touchesSystemWallpaper, let original = settings.originalWallpaper,
              FileManager.default.fileExists(atPath: original.path) else { return }
        for screen in NSScreen.screens {
            try? NSWorkspace.shared.setDesktopImageURL(original, for: screen, options: [:])
        }
    }

    func applyAudio() {
        player?.isMuted = !settings.sound
        player?.volume = settings.volume
    }

    func applyFill() {
        for s in screens { s.layer.videoGravity = settings.fillMode.gravity }
    }

    func rebuildWindows() {
        tearDownWindows()
        guard let p = player else { return }
        let targets = settings.displayMode == .all ? NSScreen.screens : Array(NSScreen.screens.prefix(1))
        for screen in targets {
            let window = WallpaperWindow(screen: screen)
            let host = NSView(frame: NSRect(origin: .zero, size: screen.frame.size))
            host.wantsLayer = true
            host.layer?.backgroundColor = NSColor.black.cgColor
            let layer = AVPlayerLayer(player: p)
            layer.videoGravity = settings.fillMode.gravity
            layer.frame = host.bounds
            layer.autoresizingMask = [.layerWidthSizable, .layerHeightSizable]
            host.layer?.addSublayer(layer)
            window.contentView = host
            window.setFrame(screen.frame, display: false)
            window.orderFrontRegardless()
            // мягкое появление
            let fade = CABasicAnimation(keyPath: "opacity")
            fade.fromValue = 0
            fade.toValue = 1
            fade.duration = 0.5
            layer.add(fade, forKey: "fadeIn")
            screens.append((window, layer))
        }
    }

    private func tearDownWindows() {
        for s in screens {
            s.layer.player = nil
            s.window.orderOut(nil)
            s.window.close()
        }
        screens.removeAll()
    }

    // MARK: пауза

    var pauseReason: PauseReason? {
        if settings.paused { return .user }
        if screensAsleep { return .sleep }
        if settings.pauseOnBattery && onBattery { return .battery }
        if settings.pauseWhenCovered && covered { return .covered }
        return nil
    }

    func updatePlayback() {
        if let p = player {
            if pauseReason == nil {
                if p.rate == 0 { p.play() }
            } else {
                p.pause()
            }
        }
        onStateChange?()
    }

    private func poll() {
        let battery = PowerSource.onBattery()
        let cover = settings.pauseWhenCovered && player != nil ? Self.desktopCovered() : false
        if battery != onBattery || cover != covered {
            onBattery = battery
            covered = cover
            updatePlayback()
        }
    }

    /// Есть ли чужое окно на весь экран (полноэкранный режим или развёрнутое окно) — тогда обоев не видно.
    static func desktopCovered() -> Bool {
        guard let list = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] else {
            return false
        }
        let me = Int(ProcessInfo.processInfo.processIdentifier)
        let sizes = NSScreen.screens.map { (full: $0.frame.size, visible: $0.visibleFrame.size) }
        for w in list {
            guard (w[kCGWindowLayer as String] as? Int) == 0,
                  (w[kCGWindowOwnerPID as String] as? Int) != me,
                  ((w[kCGWindowAlpha as String] as? Double) ?? 1) > 0.5,
                  let dict = w[kCGWindowBounds as String] as? NSDictionary,
                  let rect = CGRect(dictionaryRepresentation: dict as CFDictionary) else { continue }
            for s in sizes where rect.width >= s.full.width - 2 && rect.height >= s.visible.height - 2 {
                return true
            }
        }
        return false
    }

    // MARK: обычные обои

    static var supportDir: URL {
        FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("TnQkoWallpaper", isDirectory: true)
    }

    private func setStaticWallpaper(from url: URL) {
        if settings.originalWallpaper == nil, let main = NSScreen.screens.first,
           let original = NSWorkspace.shared.desktopImageURL(for: main),
           !original.path.hasPrefix(Self.supportDir.path) {
            settings.originalWallpaper = original
        }
        DispatchQueue.global(qos: .utility).async {
            guard let file = Self.exportFrame(url) else { return }
            DispatchQueue.main.async {
                guard self.settings.current == url else { return }
                for screen in NSScreen.screens {
                    try? NSWorkspace.shared.setDesktopImageURL(file, for: screen, options: [:])
                }
            }
        }
    }

    /// Сохраняет кадр видео в PNG (имя каждый раз новое — macOS кэширует картинку по пути).
    static func exportFrame(_ url: URL, to dir: URL = supportDir) -> URL? {
        guard let img = Thumbnails.make(url, maxSize: .zero, at: 0.5) else { return nil }
        let fm = FileManager.default
        try? fm.createDirectory(at: dir, withIntermediateDirectories: true)
        if let old = try? fm.contentsOfDirectory(at: dir, includingPropertiesForKeys: nil) {
            for f in old where f.lastPathComponent.hasPrefix("frame-") { try? fm.removeItem(at: f) }
        }
        let out = dir.appendingPathComponent("frame-\(UUID().uuidString.prefix(8)).png")
        guard let data = NSBitmapImageRep(cgImage: img).representation(using: .png, properties: [:]),
              (try? data.write(to: out)) != nil else { return nil }
        return out
    }
}
