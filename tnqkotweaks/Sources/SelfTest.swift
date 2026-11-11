import AppKit

/// `TnQkoTweaks --selftest`: всё пишется в тестовый домен defaults, Dock / Finder не перезапускаются.
enum SelfTest {
    static func run() -> Int32 {
        var failures = 0
        func check(_ ok: Bool, _ name: String) {
            print(ok ? "ok    \(name)" : "FAIL  \(name)")
            if !ok { failures += 1 }
        }
        _ = NSApplication.shared
        NSApp.setActivationPolicy(.accessory)

        let domain = "com.tearsmilk.tnqkotweaks.selftest.\(getpid())"
        Prefs.redirectDomain = domain
        Prefs.dryRunRestarts = true
        let tmp = FileManager.default.temporaryDirectory.appendingPathComponent("tnqkotweaks-\(getpid())", isDirectory: true)
        Engine.shared = Engine(backupURL: tmp.appendingPathComponent("backup.plist"))
        defer {
            Prefs.run(["delete", domain])
            Prefs.run(["-currentHost", "delete", domain])
            try? FileManager.default.removeItem(at: tmp)
        }

        // каталог
        let all = Catalog.all
        check(Set(all.map { $0.id }).count == all.count, "id настроек уникальны (\(all.count))")
        var catalogOK = true
        for t in all {
            switch t.kind {
            case .choice(let cs):
                if !cs.contains(where: { $0.value == t.systemDefault }) { print("  нет значения по умолчанию: \(t.id)"); catalogOK = false }
            case .slider(let mn, let mx, _, _, _):
                if t.systemDefault.double < mn || t.systemDefault.double > mx { print("  по умолчанию вне диапазона: \(t.id)"); catalogOK = false }
            case .toggle:
                if case .bool = t.systemDefault {} else { catalogOK = false }
            }
        }
        check(catalogOK, "значения по умолчанию согласованы с контролами")
        check(Catalog.presets.allSatisfy { $0.values.keys.allSatisfy { Catalog.tweak($0) != nil } }, "пресеты ссылаются на существующие настройки")

        // запись / чтение / сброс для каждой настройки
        let engine = Engine.shared
        check(all.allSatisfy { engine.current($0) == $0.systemDefault }, "без ключей — значения macOS")
        var roundTrip = true
        for t in all {
            let target: TweakValue
            switch t.kind {
            case .toggle: target = .bool(!t.systemDefault.bool)
            case .slider(_, let mx, _, _, let integer): target = integer ? .int(Int(mx)) : .double(mx)
            case .choice(let cs): target = cs.last { $0.value != t.systemDefault }?.value ?? t.systemDefault
            }
            engine.set(t, target)
            let got = engine.current(t)
            if got != target { print("  \(t.id): записано \(target), прочитано \(got)"); roundTrip = false }
        }
        check(roundTrip, "каждая настройка записывается и читается")
        engine.restartNow()
        check(Set(engine.restartsDone).isSuperset(of: ["Dock", "Finder", "SystemUIServer"]), "перезапуск собран в один вызов: \(Set(engine.restartsDone).sorted())")
        check(engine.hasBackup, "исходные значения запомнены")
        engine.restoreBackup()
        let restored = all.filter { engine.current($0) != $0.systemDefault }.map { $0.id }
        check(restored.isEmpty, "«Вернуть как было» восстанавливает всё \(restored)")

        engine.applyPreset(Catalog.presets[0].values)
        check(Catalog.presets[0].values.allSatisfy { engine.current(Catalog.tweak($0.key)!) == $0.value }, "пресет «\(Catalog.presets[0].title)»")
        for t in all { engine.reset(t) }
        check(all.allSatisfy { engine.current($0) == $0.systemDefault }, "сброс к стандартным значениям")
        let corner = Catalog.tweak("corner.tl")!
        engine.set(corner, .int(13))
        check((Prefs.read("com.apple.dock", "wvous-tl-modifier") as? NSNumber)?.intValue == 0, "угол экрана пишет и модификатор")

        // счётчики
        let stats = Stats()
        _ = stats.cpu()
        _ = stats.network()
        Thread.sleep(forTimeInterval: 0.3)
        let cpu = stats.cpu()
        check(cpu.map { $0 >= 0 && $0 <= 1 } ?? false, "загрузка CPU: \(cpu.map { String(format: "%.0f%%", $0 * 100) } ?? "нет")")
        let mem = stats.memoryUsed() ?? 0
        check(mem > 0 && mem < stats.memoryTotal, "память: \(Stats.bytes(Double(mem))) из \(Stats.bytes(Double(stats.memoryTotal)))")
        check(stats.network() != nil, "сеть")
        check(Stats.bytes(1536, perSecond: true) == "1.5 КБ/с", "формат скорости")

        // окно
        let w = MainWindowController()
        w.window?.orderFront(nil)
        for i in 0..<w.pages.count { w.show(page: i) }
        w.show(page: 1)
        check(w.rowCount == Catalog.sections[0].tweaks.count, "окно: все страницы строятся")
        w.close()

        if Bundle.main.bundleURL.pathExtension == "app" {
            check(Bundle.main.url(forResource: "AppIcon", withExtension: "icns") != nil, "иконка в бандле")
        }
        print(failures == 0 ? "selftest: OK" : "selftest: \(failures) FAIL")
        return failures == 0 ? 0 : 1
    }
}
