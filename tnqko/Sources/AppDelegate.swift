import AppKit

final class AppDelegate: NSObject, NSApplicationDelegate, NSMenuDelegate {
    let settings = Settings.shared
    lazy var wallpaper = WallpaperController(settings: settings)
    private var statusItem: NSStatusItem?
    private var library: LibraryWindowController?
    private var menuActions: [Action] = []

    func applicationDidFinishLaunching(_ notification: Notification) {
        buildMainMenu()
        let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        let image = NSImage(systemSymbolName: "play.rectangle.on.rectangle", accessibilityDescription: "TnQkoWallpaper")
        image?.isTemplate = true
        item.button?.image = image
        item.button?.toolTip = "TnQkoWallpaper"
        let menu = NSMenu()
        menu.delegate = self
        item.menu = menu
        statusItem = item

        wallpaper.onStateChange = { [weak self] in self?.library?.refreshState() }
        wallpaper.start()
        // при автозапуске окно не показываем, если обои уже выбраны
        if !CommandLine.arguments.contains("--login") || wallpaper.currentURL == nil { showLibrary() }
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        showLibrary()
        return false
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }

    func showLibrary() {
        if library == nil {
            let lw = LibraryWindowController(wallpaper: wallpaper)
            // без окна живём только в строке меню, иконка в Dock не нужна
            lw.onClose = { NSApp.setActivationPolicy(.accessory) }
            library = lw
        }
        NSApp.setActivationPolicy(.regular)
        library?.reload()
        library?.refreshState()
        library?.showWindow(nil)
        library?.window?.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    // MARK: меню в строке меню

    private func item(_ title: String, key: String = "", on: Bool = false, enabled: Bool = true, _ fn: @escaping () -> Void) -> NSMenuItem {
        let a = Action { _ in fn() }
        menuActions.append(a)
        let mi = NSMenuItem(title: title, action: #selector(Action.run(_:)), keyEquivalent: key)
        mi.target = a
        mi.state = on ? .on : .off
        mi.isEnabled = enabled
        return mi
    }

    func menuNeedsUpdate(_ menu: NSMenu) {
        menu.removeAllItems()
        menuActions.removeAll()
        menu.autoenablesItems = false
        let current = wallpaper.currentURL
        let header = NSMenuItem(title: current.map { "▶ " + $0.deletingPathExtension().lastPathComponent } ?? "Обои не выбраны", action: nil, keyEquivalent: "")
        header.isEnabled = false
        menu.addItem(header)
        if current != nil, let reason = wallpaper.pauseReason {
            let r = NSMenuItem(title: reason.rawValue, action: nil, keyEquivalent: "")
            r.isEnabled = false
            menu.addItem(r)
        }
        menu.addItem(.separator())
        menu.addItem(item("Открыть библиотеку…", key: "o") { [weak self] in self?.showLibrary() })
        menu.addItem(item(settings.paused ? "Продолжить" : "Пауза", enabled: current != nil) { [weak self] in
            guard let self = self else { return }
            self.settings.paused.toggle()
            self.wallpaper.updatePlayback()
        })
        menu.addItem(item("Со звуком", on: settings.sound, enabled: current != nil) { [weak self] in
            guard let self = self else { return }
            self.settings.sound.toggle()
            self.wallpaper.applyAudio()
            self.library?.refreshState()
        })

        let videos = settings.library.filter { FileManager.default.fileExists(atPath: $0.path) }
        if !videos.isEmpty {
            let sub = NSMenu()
            sub.autoenablesItems = false
            for url in videos.prefix(15) {
                sub.addItem(item(url.deletingPathExtension().lastPathComponent, on: url.standardizedFileURL.path == current?.standardizedFileURL.path) { [weak self] in
                    self?.settings.paused = false
                    self?.wallpaper.setVideo(url)
                })
            }
            let parent = NSMenuItem(title: "Библиотека", action: nil, keyEquivalent: "")
            parent.submenu = sub
            menu.addItem(parent)
        }
        menu.addItem(item("Убрать обои", enabled: current != nil) { [weak self] in self?.wallpaper.clear() })
        menu.addItem(.separator())
        menu.addItem(item("Выйти из TnQkoWallpaper", key: "q") { NSApp.terminate(nil) })
    }

    // MARK: главное меню (видно, пока открыто окно библиотеки)

    private func buildMainMenu() {
        let main = NSMenu()
        let appItem = NSMenuItem()
        main.addItem(appItem)
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "О программе TnQkoWallpaper", action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)), keyEquivalent: "")
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Скрыть TnQkoWallpaper", action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Выйти из TnQkoWallpaper", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        appItem.submenu = appMenu

        let windowItem = NSMenuItem()
        main.addItem(windowItem)
        let windowMenu = NSMenu(title: "Окно")
        windowMenu.addItem(withTitle: "Свернуть", action: #selector(NSWindow.performMiniaturize(_:)), keyEquivalent: "m")
        windowMenu.addItem(withTitle: "Закрыть", action: #selector(NSWindow.performClose(_:)), keyEquivalent: "w")
        windowItem.submenu = windowMenu
        NSApp.mainMenu = main
        NSApp.windowsMenu = windowMenu
    }
}
