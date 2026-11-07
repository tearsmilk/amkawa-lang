import AppKit

/// Одно окно: список песен → игра → итоги.
final class AppDelegate: NSObject, NSApplicationDelegate, SongSelectDelegate, GameViewDelegate {
    let settings = Settings.shared
    let library = Library()
    lazy var sounds = HitSounds()
    private(set) var window: NSWindow!
    private(set) var songSelect: SongSelectView!
    private var game: GameView?
    private var menuActions: [Action] = []

    func applicationDidFinishLaunching(_ notification: Notification) {
        buildMenu()
        let w = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1280, height: 800),
                         styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
                         backing: .buffered, defer: false)
        w.title = "TnQkoMusically"
        w.titlebarAppearsTransparent = true
        w.titleVisibility = .hidden
        w.appearance = NSAppearance(named: .darkAqua)
        w.minSize = NSSize(width: 960, height: 620)
        w.collectionBehavior = [.fullScreenPrimary]
        w.backgroundColor = Theme.background
        w.setFrameAutosaveName("TnQkoMusicallyMain")
        if !w.setFrameUsingName("TnQkoMusicallyMain") { w.center() }
        window = w
        songSelect = SongSelectView(library: library, settings: settings)
        songSelect.delegate = self
        w.contentView = songSelect
        w.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    func application(_ sender: NSApplication, open urls: [URL]) {
        // двойной клик по .osz / .osu в Finder
        if songSelect == nil { DispatchQueue.main.async { self.application(sender, open: urls) }; return }
        backToList()
        songSelect.importFiles(urls)
    }

    // MARK: переходы

    func songSelect(play map: Beatmap) { play(map) }

    private func play(_ map: Beatmap) {
        guard let audio = map.audioURL else { return }
        let clock: MusicClock
        do {
            clock = try MusicClock(url: audio)
        } catch {
            let alert = NSAlert()
            alert.messageText = "Не получается открыть музыку"
            alert.informativeText = "\(map.audioFilename): \(error.localizedDescription)\n\nmacOS не проигрывает OGG — такую карту нужно перекодировать в mp3."
            alert.beginSheetModal(for: window)
            songSelect.resumePreview()
            return
        }
        clock.volume = settings.musicVolume
        clock.offsetMs = settings.offsetMs
        sounds.volume = settings.effectsVolume
        // карта перечитывается с диска, чтобы состояние объектов было чистым
        let fresh = (map.fileURL.flatMap { try? OsuParser.parse(url: $0) }) ?? map
        let g = GameView(map: fresh, clock: clock, sounds: sounds, settings: settings)
        g.delegate = self
        game = g
        window.contentView = g
        g.start()
    }

    private func backToList() {
        game?.teardown()
        game = nil
        window.contentView = songSelect
        songSelect.reload()
        window.makeFirstResponder(songSelect)
    }

    func gameFinished(_ view: GameView, session: GameSession) {
        let isRecord = settings.submit(session.map.key, Settings.Record(score: session.score, accuracy: session.accuracy, combo: session.maxCombo, grade: session.grade))
        let map = session.map
        window.contentView = ResultsView(session: session, isRecord: isRecord, onRetry: { [weak self] in self?.play(map) }, onBack: { [weak self] in self?.backToList() })
        game = nil
    }

    func gameRestart(_ view: GameView) {
        let map = view.map
        view.teardown()
        play(map)
    }

    func gameQuit(_ view: GameView) { backToList() }

    // MARK: меню

    private func buildMenu() {
        let main = NSMenu()
        let appItem = NSMenuItem()
        main.addItem(appItem)
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "О программе TnQkoMusically", action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)), keyEquivalent: "")
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Скрыть TnQkoMusically", action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
        appMenu.addItem(withTitle: "Выйти из TnQkoMusically", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        appItem.submenu = appMenu

        let fileItem = NSMenuItem()
        main.addItem(fileItem)
        let fileMenu = NSMenu(title: "Файл")
        fileMenu.addItem(item("Добавить трек…", "o") { [weak self] in self?.backToList(); self?.songSelect.pickFiles(audio: true) })
        fileMenu.addItem(item("Импорт карты osu!…", "i") { [weak self] in self?.backToList(); self?.songSelect.pickFiles(audio: false) })
        fileMenu.addItem(item("Открыть папку песен", "") { [weak self] in
            if let dir = self?.library.songsDir { NSWorkspace.shared.open(dir) }
        })
        fileItem.submenu = fileMenu

        let viewItem = NSMenuItem()
        main.addItem(viewItem)
        let viewMenu = NSMenu(title: "Вид")
        let fs = NSMenuItem(title: "Полный экран", action: #selector(NSWindow.toggleFullScreen(_:)), keyEquivalent: "f")
        fs.keyEquivalentModifierMask = [.control, .command]
        viewMenu.addItem(fs)
        viewItem.submenu = viewMenu

        let windowItem = NSMenuItem()
        main.addItem(windowItem)
        let windowMenu = NSMenu(title: "Окно")
        windowMenu.addItem(withTitle: "Свернуть", action: #selector(NSWindow.performMiniaturize(_:)), keyEquivalent: "m")
        windowItem.submenu = windowMenu
        NSApp.mainMenu = main
        NSApp.windowsMenu = windowMenu
    }

    private func item(_ title: String, _ key: String, _ fn: @escaping () -> Void) -> NSMenuItem {
        let a = Action { _ in fn() }
        menuActions.append(a)
        let mi = NSMenuItem(title: title, action: #selector(Action.run(_:)), keyEquivalent: key)
        mi.target = a
        return mi
    }
}
