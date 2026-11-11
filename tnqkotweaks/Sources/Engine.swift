import AppKit
import Foundation

/// Чтение и запись defaults. Пишем через /usr/bin/defaults — так cfprefsd сразу видит изменения.
enum Prefs {
    /// Для самопроверки: перенаправить все домены в тестовый.
    static var redirectDomain: String?
    static var dryRunRestarts = false

    static func domain(_ d: String) -> String { redirectDomain ?? d }

    static func read(_ domain: String, _ key: String, currentHost: Bool = false) -> Any? {
        let d = self.domain(domain)
        let app: CFString = d == "NSGlobalDomain" ? kCFPreferencesAnyApplication : d as CFString
        if currentHost {
            CFPreferencesSynchronize(app, kCFPreferencesCurrentUser, kCFPreferencesCurrentHost)
            return CFPreferencesCopyValue(key as CFString, app, kCFPreferencesCurrentUser, kCFPreferencesCurrentHost)
        }
        CFPreferencesSynchronize(app, kCFPreferencesCurrentUser, kCFPreferencesAnyHost)
        return CFPreferencesCopyValue(key as CFString, app, kCFPreferencesCurrentUser, kCFPreferencesAnyHost)
    }

    @discardableResult
    static func write(_ domain: String, _ key: String, _ value: TweakValue, currentHost: Bool = false) -> Bool {
        run((currentHost ? ["-currentHost"] : []) + ["write", self.domain(domain), key] + value.args)
    }

    @discardableResult
    static func delete(_ domain: String, _ key: String, currentHost: Bool = false) -> Bool {
        run((currentHost ? ["-currentHost"] : []) + ["delete", self.domain(domain), key])
    }

    @discardableResult
    static func run(_ args: [String], tool: String = "/usr/bin/defaults") -> Bool {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: tool)
        p.arguments = args
        p.standardOutput = FileHandle.nullDevice
        p.standardError = FileHandle.nullDevice
        do { try p.run() } catch { return false }
        p.waitUntilExit()
        return p.terminationStatus == 0
    }
}

/// Действия, которым мало `defaults write`.
enum SystemActions {
    static func setAppearance(_ v: TweakValue) {
        guard case .string(let mode) = v else { return }
        if mode == "Auto" {
            Prefs.write("NSGlobalDomain", "AppleInterfaceStyleSwitchesAutomatically", .bool(true))
        } else {
            Prefs.write("NSGlobalDomain", "AppleInterfaceStyleSwitchesAutomatically", .bool(false))
            guard Prefs.redirectDomain == nil else { return }
            // System Events переключает тему сразу и везде (macOS один раз спросит разрешение)
            let script = "tell application \"System Events\" to tell appearance preferences to set dark mode to \(mode == "Dark" ? "true" : "false")"
            var error: NSDictionary?
            NSAppleScript(source: script)?.executeAndReturnError(&error)
            if error != nil {
                if mode == "Dark" { Prefs.write("NSGlobalDomain", "AppleInterfaceStyle", .string("Dark")) } else { Prefs.delete("NSGlobalDomain", "AppleInterfaceStyle") }
                notify("AppleInterfaceThemeChangedNotification")
            }
        }
    }

    static func setAccent(_ index: Int) {
        guard Catalog.accentColors.indices.contains(index) else { return }
        let (_, code, highlight) = Catalog.accentColors[index]
        if let c = code { Prefs.write("NSGlobalDomain", "AppleAccentColor", .int(c)) } else { Prefs.delete("NSGlobalDomain", "AppleAccentColor") }
        Prefs.write("NSGlobalDomain", "AppleHighlightColor", .string(highlight))
        notify("AppleColorPreferencesChangedNotification")
        notify("AppleAquaColorVariantChanged")
    }

    static func notify(_ name: String) {
        guard Prefs.redirectDomain == nil else { return }
        DistributedNotificationCenter.default().postNotificationName(NSNotification.Name(name), object: nil, userInfo: nil, deliverImmediately: true)
    }

    /// Разделитель в Dock (пустая плитка), который можно перетащить куда угодно.
    static func addDockSpacer() {
        Prefs.run(["write", Prefs.domain("com.apple.dock"), "persistent-apps", "-array-add", "{\"tile-type\"=\"spacer-tile\";}"])
        Engine.shared.scheduleRestart(["Dock"])
    }
}

/// Применение настроек, резервная копия исходных значений, отложенный перезапуск Dock / Finder.
final class Engine {
    static var shared = Engine()

    private var pendingRestart = Set<String>()
    private var restartWork: DispatchWorkItem?
    private(set) var restartsDone: [String] = []
    var backupURL: URL

    init(backupURL: URL? = nil) {
        self.backupURL = backupURL ?? FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("TnQkoTweaks/backup.plist")
    }

    func current(_ t: Tweak) -> TweakValue {
        if let r = t.read, let v = r() { return v }
        return TweakValue.from(Prefs.read(t.domain, t.key, currentHost: t.currentHost), like: t.systemDefault) ?? t.systemDefault
    }

    func isChanged(_ t: Tweak) -> Bool { current(t) != t.systemDefault }

    func set(_ t: Tweak, _ v: TweakValue) {
        rememberOriginal(t)
        if let apply = t.apply {
            apply(v)
        } else {
            Prefs.write(t.domain, t.key, v, currentHost: t.currentHost)
        }
        for (d, k, cv) in t.companions?(v) ?? [] {
            if let cv = cv { Prefs.write(d, k, cv) } else { Prefs.delete(d, k) }
        }
        scheduleRestart(t.restart)
    }

    /// Вернуть стандартное значение macOS (удалить ключ).
    func reset(_ t: Tweak) {
        rememberOriginal(t)
        if t.apply != nil { t.apply?(t.systemDefault) } else { Prefs.delete(t.domain, t.key, currentHost: t.currentHost) }
        scheduleRestart(t.restart)
    }

    func applyPreset(_ values: [String: TweakValue]) {
        for (id, v) in values { if let t = Catalog.tweak(id) { set(t, v) } }
    }

    // MARK: резервная копия

    private func loadBackup() -> [String: Any] {
        guard let data = try? Data(contentsOf: backupURL),
              let plist = try? PropertyListSerialization.propertyList(from: data, format: nil) as? [String: Any] else { return [:] }
        return plist
    }

    private func saveBackup(_ b: [String: Any]) {
        try? FileManager.default.createDirectory(at: backupURL.deletingLastPathComponent(), withIntermediateDirectories: true)
        if let data = try? PropertyListSerialization.data(fromPropertyList: b, format: .xml, options: 0) { try? data.write(to: backupURL) }
    }

    /// Запоминает значение, которое было до первого изменения этой настройки.
    private func rememberOriginal(_ t: Tweak) {
        var b = loadBackup()
        guard b[t.id] == nil else { return }
        if t.read != nil {
            b[t.id] = ["value": current(t).plist]
        } else if let v = Prefs.read(t.domain, t.key, currentHost: t.currentHost) {
            b[t.id] = ["value": v]
        } else {
            b[t.id] = ["absent": true]
        }
        saveBackup(b)
    }

    var hasBackup: Bool { !loadBackup().isEmpty }

    /// Возвращает всё, что меняла программа, к значениям до первого запуска.
    func restoreBackup() {
        let b = loadBackup()
        var restarts = Set<String>()
        for (id, entry) in b {
            guard let t = Catalog.tweak(id), let e = entry as? [String: Any] else { continue }
            if e["absent"] != nil {
                if t.apply != nil { t.apply?(t.systemDefault) } else { Prefs.delete(t.domain, t.key, currentHost: t.currentHost) }
            } else if let v = TweakValue.from(e["value"], like: t.systemDefault) {
                if let apply = t.apply { apply(v) } else { Prefs.write(t.domain, t.key, v, currentHost: t.currentHost) }
            }
            restarts.formUnion(t.restart)
        }
        try? FileManager.default.removeItem(at: backupURL)
        scheduleRestart(Array(restarts))
    }

    // MARK: перезапуск

    func scheduleRestart(_ names: [String]) {
        guard !names.isEmpty else { return }
        pendingRestart.formUnion(names)
        restartWork?.cancel()
        let work = DispatchWorkItem { [weak self] in self?.restartNow() }
        restartWork = work
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.8, execute: work)
    }

    func restartNow() {
        let names = Array(pendingRestart).sorted()
        pendingRestart.removeAll()
        guard !names.isEmpty else { return }
        restartsDone.append(contentsOf: names)
        if Prefs.dryRunRestarts { return }
        // Dock, Finder, SystemUIServer, ControlCenter macOS сама сразу запускает заново
        Prefs.run(names, tool: "/usr/bin/killall")
    }
}
