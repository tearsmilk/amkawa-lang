import AppKit

final class AppDelegate: NSObject, NSApplicationDelegate {
    private var main: MainWindowController?

    func applicationDidFinishLaunching(_ notification: Notification) {
        buildMenu()
        Widgets.shared.onOpen = { [weak self] in self?.showWindow() }
        Widgets.shared.start()
        // при автозапуске — только счётчики в строке меню
        if CommandLine.arguments.contains("--login") && Widgets.shared.anyEnabled {
            NSApp.setActivationPolicy(.accessory)
        } else {
            showWindow()
        }
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        showWindow()
        return false
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }

    func showWindow() {
        if main == nil {
            let m = MainWindowController()
            m.onClose = { [weak self] in self?.windowClosed() }
            main = m
        }
        NSApp.setActivationPolicy(.regular)
        main?.showWindow(nil)
        main?.window?.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    /// Окно закрыто: если счётчики включены — остаёмся тихо в строке меню, иначе выходим (настройки уже записаны).
    private func windowClosed() {
        Engine.shared.restartNow()
        if Widgets.shared.anyEnabled {
            NSApp.setActivationPolicy(.accessory)
        } else {
            NSApp.terminate(nil)
        }
    }

    func applicationWillTerminate(_ notification: Notification) { Engine.shared.restartNow() }

    private func buildMenu() {
        let main = NSMenu()
        let appItem = NSMenuItem()
        main.addItem(appItem)
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "О программе TnQkoTweaks", action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)), keyEquivalent: "")
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Скрыть TnQkoTweaks", action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
        appMenu.addItem(withTitle: "Выйти из TnQkoTweaks", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
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
