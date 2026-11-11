import Foundation

/// Значение настройки: то, что пишется в defaults.
enum TweakValue: Equatable {
    case bool(Bool), int(Int), double(Double), string(String)

    var plist: Any {
        switch self {
        case .bool(let v): return v
        case .int(let v): return v
        case .double(let v): return v
        case .string(let v): return v
        }
    }

    /// Аргументы для `defaults write`.
    var args: [String] {
        switch self {
        case .bool(let v): return ["-bool", v ? "true" : "false"]
        case .int(let v): return ["-int", String(v)]
        case .double(let v): return ["-float", String(v)]
        case .string(let v): return ["-string", v]
        }
    }

    static func from(_ any: Any?, like sample: TweakValue) -> TweakValue? {
        guard let any = any else { return nil }
        switch sample {
        case .bool: return (any as? NSNumber).map { .bool($0.boolValue) } ?? (any as? String).map { .bool(["1", "true", "yes"].contains($0.lowercased())) }
        case .int: return (any as? NSNumber).map { .int($0.intValue) } ?? (any as? String).flatMap { Int($0) }.map { .int($0) }
        case .double: return (any as? NSNumber).map { .double($0.doubleValue) } ?? (any as? String).flatMap { Double($0) }.map { .double($0) }
        case .string: return (any as? String).map { .string($0) } ?? (any as? NSNumber).map { .string($0.stringValue) }
        }
    }

    var bool: Bool { if case .bool(let v) = self { return v }; return false }
    var double: Double {
        switch self {
        case .int(let v): return Double(v)
        case .double(let v): return v
        default: return 0
        }
    }
}

struct Choice {
    let title: String
    let value: TweakValue
}

enum TweakKind {
    /// inverted — переключатель показывает «включено», когда в defaults записано false.
    case toggle(inverted: Bool)
    case slider(min: Double, max: Double, step: Double, unit: String, integer: Bool)
    case choice([Choice])
}

/// Одна настройка macOS: домен + ключ defaults, вид контрола, какие процессы перезапустить.
struct Tweak {
    let id: String
    let title: String
    var hint: String = ""
    let domain: String
    let key: String
    var currentHost = false
    let kind: TweakKind
    /// Что macOS считает значением, когда ключа нет.
    let systemDefault: TweakValue
    var restart: [String] = []
    /// Пометка вроде «после перезахода».
    var note: String?
    /// Особая запись (например, тёмная тема через System Events); иначе — `defaults write`.
    var apply: ((TweakValue) -> Void)?
    /// Особое чтение.
    var read: (() -> TweakValue?)?
    /// Дополнительные ключи, которые надо писать вместе (domain, key, value для данного значения).
    var companions: ((TweakValue) -> [(String, String, TweakValue?)])?
}

struct Section {
    let id: String
    let title: String
    let symbol: String
    let subtitle: String
    let tweaks: [Tweak]
}

enum Catalog {
    static let global = "NSGlobalDomain"
    static let dock = "com.apple.dock"
    static let finder = "com.apple.finder"
    static let shots = "com.apple.screencapture"
    static let clock = "com.apple.menuextra.clock"

    static let corners: [Choice] = [
        Choice(title: "Ничего", value: .int(1)),
        Choice(title: "Mission Control", value: .int(2)),
        Choice(title: "Окна программы", value: .int(3)),
        Choice(title: "Рабочий стол", value: .int(4)),
        Choice(title: "Заставка", value: .int(5)),
        Choice(title: "Сон дисплея", value: .int(10)),
        Choice(title: "Launchpad", value: .int(11)),
        Choice(title: "Центр уведомлений", value: .int(12)),
        Choice(title: "Заблокировать экран", value: .int(13)),
    ]

    static func corner(_ id: String, _ title: String, _ code: String, _ def: Int) -> Tweak {
        var t = Tweak(id: "corner.\(id)", title: title, domain: dock, key: "wvous-\(code)-corner", kind: .choice(corners), systemDefault: .int(def), restart: ["Dock"])
        t.companions = { _ in [(dock, "wvous-\(code)-modifier", .int(0))] }
        return t
    }

    static let accentColors: [(String, Int?, String)] = [
        ("Синий (как в macOS)", nil, "0.698039 0.843137 1.000000 Blue"),
        ("Графит", -1, "0.847059 0.847059 0.862745 Graphite"),
        ("Красный", 0, "1.000000 0.733333 0.721569 Red"),
        ("Оранжевый", 1, "1.000000 0.874510 0.701961 Orange"),
        ("Жёлтый", 2, "1.000000 0.937255 0.690196 Yellow"),
        ("Зелёный", 3, "0.752941 0.964706 0.678431 Green"),
        ("Фиолетовый", 5, "0.968627 0.831373 1.000000 Purple"),
        ("Розовый", 6, "1.000000 0.749020 0.823529 Pink"),
    ]

    static var sections: [Section] {
        var appearance = Tweak(id: "look.theme", title: "Оформление", hint: "Светлое, тёмное или по времени суток",
                               domain: global, key: "AppleInterfaceStyle",
                               kind: .choice([Choice(title: "Светлое", value: .string("Light")), Choice(title: "Тёмное", value: .string("Dark")), Choice(title: "Автоматически", value: .string("Auto"))]),
                               systemDefault: .string("Light"))
        appearance.read = {
            if Prefs.read(global, "AppleInterfaceStyleSwitchesAutomatically").map({ ($0 as? NSNumber)?.boolValue ?? false }) == true { return .string("Auto") }
            return (Prefs.read(global, "AppleInterfaceStyle") as? String) == "Dark" ? .string("Dark") : .string("Light")
        }
        appearance.apply = { v in SystemActions.setAppearance(v) }

        var accent = Tweak(id: "look.accent", title: "Акцентный цвет", hint: "Кнопки, переключатели и выделение текста",
                           domain: global, key: "AppleAccentColor",
                           kind: .choice(accentColors.enumerated().map { Choice(title: $0.element.0, value: .int($0.offset)) }),
                           systemDefault: .int(0))
        accent.read = {
            guard let raw = Prefs.read(global, "AppleAccentColor") as? NSNumber else { return .int(0) }
            return .int(accentColors.firstIndex { $0.1 == raw.intValue } ?? 0)
        }
        accent.apply = { v in SystemActions.setAccent(Int(v.double)) }
        accent.note = "часть программ — после перезапуска"

        return [
            Section(id: "dock", title: "Dock", symbol: "dock.rectangle", subtitle: "Размер, положение, анимации и поведение панели Dock", tweaks: [
                Tweak(id: "dock.autohide", title: "Автоматически скрывать Dock", domain: dock, key: "autohide", kind: .toggle(inverted: false), systemDefault: .bool(false), restart: ["Dock"]),
                Tweak(id: "dock.delay", title: "Задержка перед появлением", hint: "0 — Dock выезжает сразу", domain: dock, key: "autohide-delay",
                      kind: .slider(min: 0, max: 1.5, step: 0.05, unit: "с", integer: false), systemDefault: .double(0.5), restart: ["Dock"]),
                Tweak(id: "dock.speed", title: "Длительность выезда", hint: "Меньше — быстрее", domain: dock, key: "autohide-time-modifier",
                      kind: .slider(min: 0, max: 1.5, step: 0.05, unit: "с", integer: false), systemDefault: .double(1.0), restart: ["Dock"]),
                Tweak(id: "dock.size", title: "Размер значков", domain: dock, key: "tilesize",
                      kind: .slider(min: 16, max: 128, step: 2, unit: "px", integer: true), systemDefault: .int(48), restart: ["Dock"]),
                Tweak(id: "dock.magnify", title: "Увеличение при наведении", domain: dock, key: "magnification", kind: .toggle(inverted: false), systemDefault: .bool(false), restart: ["Dock"]),
                Tweak(id: "dock.large", title: "Размер при увеличении", domain: dock, key: "largesize",
                      kind: .slider(min: 16, max: 128, step: 2, unit: "px", integer: true), systemDefault: .int(128), restart: ["Dock"]),
                Tweak(id: "dock.position", title: "Положение на экране", domain: dock, key: "orientation",
                      kind: .choice([Choice(title: "Снизу", value: .string("bottom")), Choice(title: "Слева", value: .string("left")), Choice(title: "Справа", value: .string("right"))]),
                      systemDefault: .string("bottom"), restart: ["Dock"]),
                Tweak(id: "dock.effect", title: "Эффект сворачивания окон", domain: dock, key: "mineffect",
                      kind: .choice([Choice(title: "Джинн", value: .string("genie")), Choice(title: "Масштаб", value: .string("scale")), Choice(title: "Засасывание", value: .string("suck"))]),
                      systemDefault: .string("genie"), restart: ["Dock"]),
                Tweak(id: "dock.minToApp", title: "Сворачивать окна в значок программы", domain: dock, key: "minimize-to-application", kind: .toggle(inverted: false), systemDefault: .bool(false), restart: ["Dock"]),
                Tweak(id: "dock.recents", title: "Недавние программы в Dock", domain: dock, key: "show-recents", kind: .toggle(inverted: false), systemDefault: .bool(true), restart: ["Dock"]),
                Tweak(id: "dock.static", title: "Показывать только запущенные программы", domain: dock, key: "static-only", kind: .toggle(inverted: false), systemDefault: .bool(false), restart: ["Dock"]),
                Tweak(id: "dock.dots", title: "Точки под запущенными программами", domain: dock, key: "show-process-indicators", kind: .toggle(inverted: false), systemDefault: .bool(true), restart: ["Dock"]),
                Tweak(id: "dock.bounce", title: "Прыжки значка при запуске", domain: dock, key: "launchanim", kind: .toggle(inverted: false), systemDefault: .bool(true), restart: ["Dock"]),
                Tweak(id: "dock.hidden", title: "Полупрозрачные значки скрытых программ", domain: dock, key: "showhidden", kind: .toggle(inverted: false), systemDefault: .bool(false), restart: ["Dock"]),
            ]),
            Section(id: "look", title: "Оформление", symbol: "paintpalette", subtitle: "Тема, цвет акцента, окна и анимации", tweaks: [
                appearance,
                accent,
                Tweak(id: "look.tinting", title: "Окна подкрашиваются цветом обоев", domain: global, key: "AppleReduceDesktopTinting", kind: .toggle(inverted: true), systemDefault: .bool(false)),
                Tweak(id: "look.scrollbars", title: "Полосы прокрутки", domain: global, key: "AppleShowScrollBars",
                      kind: .choice([Choice(title: "Автоматически", value: .string("Automatic")), Choice(title: "При прокрутке", value: .string("WhenScrolling")), Choice(title: "Всегда", value: .string("Always"))]),
                      systemDefault: .string("Automatic"), note: "в открытых программах — после перезапуска"),
                Tweak(id: "look.sidebar", title: "Значки в боковом меню", domain: global, key: "NSTableViewDefaultSizeMode",
                      kind: .choice([Choice(title: "Маленькие", value: .int(1)), Choice(title: "Средние", value: .int(2)), Choice(title: "Крупные", value: .int(3))]),
                      systemDefault: .int(2), note: "в открытых программах — после перезапуска"),
                Tweak(id: "look.doubleclick", title: "Двойной клик по заголовку окна", domain: global, key: "AppleActionOnDoubleClick",
                      kind: .choice([Choice(title: "Развернуть", value: .string("Maximize")), Choice(title: "Свернуть", value: .string("Minimize")), Choice(title: "Ничего", value: .string("None"))]),
                      systemDefault: .string("Maximize")),
                Tweak(id: "look.windowAnim", title: "Анимация открытия окон", hint: "Выключите — окна появляются мгновенно", domain: global, key: "NSAutomaticWindowAnimationsEnabled",
                      kind: .toggle(inverted: false), systemDefault: .bool(true), note: "в открытых программах — после перезапуска"),
                Tweak(id: "look.resize", title: "Скорость изменения размера окон", hint: "Меньше — быстрее", domain: global, key: "NSWindowResizeTime",
                      kind: .slider(min: 0.001, max: 0.4, step: 0.01, unit: "с", integer: false), systemDefault: .double(0.2), note: "в открытых программах — после перезапуска"),
                Tweak(id: "look.mission", title: "Скорость анимации Mission Control", hint: "Меньше — быстрее", domain: dock, key: "expose-animation-duration",
                      kind: .slider(min: 0, max: 1, step: 0.05, unit: "с", integer: false), systemDefault: .double(0.5), restart: ["Dock"]),
                Tweak(id: "look.spaces", title: "Переставлять рабочие столы по использованию", domain: dock, key: "mru-spaces", kind: .toggle(inverted: false), systemDefault: .bool(true), restart: ["Dock"]),
                Tweak(id: "look.saveExpanded", title: "Развёрнутый диалог сохранения", domain: global, key: "NSNavPanelExpandedStateForSaveMode", kind: .toggle(inverted: false), systemDefault: .bool(false)),
                Tweak(id: "look.icloud", title: "Сохранять новые документы в iCloud", domain: global, key: "NSDocumentSaveNewDocumentsToCloud", kind: .toggle(inverted: false), systemDefault: .bool(true)),
            ]),
            Section(id: "menubar", title: "Строка меню", symbol: "menubar.rectangle", subtitle: "Часы, батарея и сама строка меню", tweaks: [
                Tweak(id: "menu.autohide", title: "Автоматически скрывать строку меню", domain: global, key: "_HIHideMenuBar", kind: .toggle(inverted: false), systemDefault: .bool(false), restart: ["Finder"], note: "в открытых программах — после перезапуска"),
                Tweak(id: "menu.seconds", title: "Секунды в часах", domain: clock, key: "ShowSeconds", kind: .toggle(inverted: false), systemDefault: .bool(false), restart: ["ControlCenter", "SystemUIServer"]),
                Tweak(id: "menu.weekday", title: "День недели в часах", domain: clock, key: "ShowDayOfWeek", kind: .toggle(inverted: false), systemDefault: .bool(true), restart: ["ControlCenter", "SystemUIServer"]),
                Tweak(id: "menu.date", title: "Дата в часах", domain: clock, key: "ShowDate",
                      kind: .choice([Choice(title: "Когда есть место", value: .int(0)), Choice(title: "Всегда", value: .int(1)), Choice(title: "Никогда", value: .int(2))]),
                      systemDefault: .int(0), restart: ["ControlCenter", "SystemUIServer"]),
                Tweak(id: "menu.analog", title: "Аналоговые часы", domain: clock, key: "IsAnalog", kind: .toggle(inverted: false), systemDefault: .bool(false), restart: ["ControlCenter", "SystemUIServer"]),
                Tweak(id: "menu.battery", title: "Проценты заряда батареи", domain: "com.apple.controlcenter", key: "BatteryShowPercentage", currentHost: true, kind: .toggle(inverted: false), systemDefault: .bool(false), restart: ["ControlCenter"]),
            ]),
            Section(id: "finder", title: "Finder", symbol: "folder", subtitle: "Скрытые файлы, расширения, панели и рабочий стол", tweaks: [
                Tweak(id: "finder.hidden", title: "Показывать скрытые файлы", hint: "То же, что ⌘⇧. в окне Finder", domain: finder, key: "AppleShowAllFiles", kind: .toggle(inverted: false), systemDefault: .bool(false), restart: ["Finder"]),
                Tweak(id: "finder.ext", title: "Показывать расширения файлов", domain: global, key: "AppleShowAllExtensions", kind: .toggle(inverted: false), systemDefault: .bool(false), restart: ["Finder"]),
                Tweak(id: "finder.extWarning", title: "Предупреждать при смене расширения", domain: finder, key: "FXEnableExtensionChangeWarning", kind: .toggle(inverted: false), systemDefault: .bool(true), restart: ["Finder"]),
                Tweak(id: "finder.path", title: "Строка пути внизу окна", domain: finder, key: "ShowPathbar", kind: .toggle(inverted: false), systemDefault: .bool(false), restart: ["Finder"]),
                Tweak(id: "finder.status", title: "Строка состояния", domain: finder, key: "ShowStatusBar", kind: .toggle(inverted: false), systemDefault: .bool(false), restart: ["Finder"]),
                Tweak(id: "finder.titlePath", title: "Полный путь в заголовке окна", domain: finder, key: "_FXShowPosixPathInTitle", kind: .toggle(inverted: false), systemDefault: .bool(false), restart: ["Finder"]),
                Tweak(id: "finder.foldersFirst", title: "Папки — выше файлов", domain: finder, key: "_FXSortFoldersFirst", kind: .toggle(inverted: false), systemDefault: .bool(false), restart: ["Finder"]),
                Tweak(id: "finder.view", title: "Вид новых окон", domain: finder, key: "FXPreferredViewStyle",
                      kind: .choice([Choice(title: "Значки", value: .string("icnv")), Choice(title: "Список", value: .string("Nlsv")), Choice(title: "Колонки", value: .string("clmv")), Choice(title: "Галерея", value: .string("glyv"))]),
                      systemDefault: .string("icnv"), restart: ["Finder"]),
                Tweak(id: "finder.search", title: "Где искать по умолчанию", domain: finder, key: "FXDefaultSearchScope",
                      kind: .choice([Choice(title: "Весь Mac", value: .string("SCev")), Choice(title: "Текущая папка", value: .string("SCcf"))]),
                      systemDefault: .string("SCev"), restart: ["Finder"]),
                Tweak(id: "finder.desktop", title: "Значки на рабочем столе", hint: "Выключите — рабочий стол станет чистым, файлы останутся в папке", domain: finder, key: "CreateDesktop", kind: .toggle(inverted: false), systemDefault: .bool(true), restart: ["Finder"]),
                Tweak(id: "finder.quit", title: "Пункт «Завершить Finder» в меню", domain: finder, key: "QuitMenuItem", kind: .toggle(inverted: false), systemDefault: .bool(false), restart: ["Finder"]),
                Tweak(id: "finder.dsstore", title: "Не создавать .DS_Store на сетевых дисках", domain: "com.apple.desktopservices", key: "DSDontWriteNetworkStores", kind: .toggle(inverted: false), systemDefault: .bool(false), restart: ["Finder"]),
            ]),
            Section(id: "shots", title: "Скриншоты", symbol: "camera.viewfinder", subtitle: "Формат, папка, тень и миниатюра", tweaks: [
                Tweak(id: "shots.type", title: "Формат", domain: shots, key: "type",
                      kind: .choice([Choice(title: "PNG", value: .string("png")), Choice(title: "JPEG", value: .string("jpg")), Choice(title: "PDF", value: .string("pdf")), Choice(title: "TIFF", value: .string("tiff"))]),
                      systemDefault: .string("png"), restart: ["SystemUIServer"]),
                { () -> Tweak in
                    var t = Tweak(id: "shots.location", title: "Куда сохранять", domain: shots, key: "location",
                                  kind: .choice([Choice(title: "Рабочий стол", value: .string("~/Desktop")), Choice(title: "Загрузки", value: .string("~/Downloads")), Choice(title: "Документы", value: .string("~/Documents")), Choice(title: "Изображения/Скриншоты", value: .string("~/Pictures/Screenshots"))]),
                                  systemDefault: .string("~/Desktop"), restart: ["SystemUIServer"])
                    t.read = {
                        guard let raw = Prefs.read(shots, "location") as? String else { return .string("~/Desktop") }
                        return .string((raw as NSString).abbreviatingWithTildeInPath)
                    }
                    t.apply = { v in
                        guard case .string(let s) = v else { return }
                        let path = (s as NSString).expandingTildeInPath
                        try? FileManager.default.createDirectory(atPath: path, withIntermediateDirectories: true)
                        Prefs.write(shots, "location", .string(path))
                    }
                    return t
                }(),
                Tweak(id: "shots.shadow", title: "Тень у окон на скриншотах", domain: shots, key: "disable-shadow", kind: .toggle(inverted: true), systemDefault: .bool(false), restart: ["SystemUIServer"]),
                Tweak(id: "shots.thumb", title: "Миниатюра в углу после снимка", domain: shots, key: "show-thumbnail", kind: .toggle(inverted: false), systemDefault: .bool(true), restart: ["SystemUIServer"]),
                Tweak(id: "shots.date", title: "Дата и время в имени файла", domain: shots, key: "include-date", kind: .toggle(inverted: false), systemDefault: .bool(true), restart: ["SystemUIServer"]),
            ]),
            Section(id: "corners", title: "Углы экрана", symbol: "rectangle.dashed", subtitle: "Что происходит, когда курсор упирается в угол", tweaks: [
                corner("tl", "Левый верхний", "tl", 1),
                corner("tr", "Правый верхний", "tr", 1),
                corner("bl", "Левый нижний", "bl", 1),
                corner("br", "Правый нижний", "br", 1),
            ]),
            Section(id: "keyboard", title: "Клавиатура и текст", symbol: "keyboard", subtitle: "Повтор клавиш и автозамены", tweaks: [
                Tweak(id: "kb.repeat", title: "Скорость повтора", hint: "Меньше — быстрее (2 — очень быстро)", domain: global, key: "KeyRepeat",
                      kind: .slider(min: 1, max: 15, step: 1, unit: "", integer: true), systemDefault: .int(6), note: "после перезахода в систему"),
                Tweak(id: "kb.delay", title: "Задержка до повтора", hint: "Меньше — повтор начинается раньше", domain: global, key: "InitialKeyRepeat",
                      kind: .slider(min: 10, max: 120, step: 5, unit: "", integer: true), systemDefault: .int(25), note: "после перезахода в систему"),
                Tweak(id: "kb.accents", title: "Меню акцентов при удержании клавиши", hint: "Выключите — клавиша будет повторяться", domain: global, key: "ApplePressAndHoldEnabled",
                      kind: .toggle(inverted: false), systemDefault: .bool(true), note: "в открытых программах — после перезапуска"),
                Tweak(id: "kb.autocorrect", title: "Автоисправление", domain: global, key: "NSAutomaticSpellingCorrectionEnabled", kind: .toggle(inverted: false), systemDefault: .bool(true)),
                Tweak(id: "kb.caps", title: "Заглавная буква в начале предложения", domain: global, key: "NSAutomaticCapitalizationEnabled", kind: .toggle(inverted: false), systemDefault: .bool(true)),
                Tweak(id: "kb.period", title: "Точка по двойному пробелу", domain: global, key: "NSAutomaticPeriodSubstitutionEnabled", kind: .toggle(inverted: false), systemDefault: .bool(true)),
                Tweak(id: "kb.quotes", title: "«Умные» кавычки", domain: global, key: "NSAutomaticQuoteSubstitutionEnabled", kind: .toggle(inverted: false), systemDefault: .bool(true)),
                Tweak(id: "kb.dashes", title: "«Умные» тире", domain: global, key: "NSAutomaticDashSubstitutionEnabled", kind: .toggle(inverted: false), systemDefault: .bool(true)),
            ]),
        ]
    }

    static var all: [Tweak] { sections.flatMap { $0.tweaks } }

    static func tweak(_ id: String) -> Tweak? { all.first { $0.id == id } }

    /// Готовые наборы.
    static let presets: [(title: String, hint: String, values: [String: TweakValue])] = [
        ("Минимализм", "Dock прячется и выезжает без задержки, без недавних программ, чистый рабочий стол, путь и расширения в Finder", [
            "dock.autohide": .bool(true), "dock.delay": .double(0), "dock.speed": .double(0.4), "dock.recents": .bool(false),
            "dock.size": .int(42), "dock.effect": .string("scale"), "finder.desktop": .bool(false), "finder.path": .bool(true),
            "finder.ext": .bool(true), "finder.foldersFirst": .bool(true), "look.tinting": .bool(true),
        ]),
        ("Скорость", "Меньше анимаций: окна, Dock и Mission Control реагируют мгновенно — меньше работы для видеокарты", [
            "look.windowAnim": .bool(false), "look.resize": .double(0.001), "look.mission": .double(0.1),
            "dock.delay": .double(0), "dock.speed": .double(0.25), "dock.bounce": .bool(false), "dock.effect": .string("scale"),
            "shots.thumb": .bool(false),
        ]),
        ("Для работы с файлами", "Скрытые файлы, расширения, путь в заголовке, поиск в текущей папке, вид списком", [
            "finder.hidden": .bool(true), "finder.ext": .bool(true), "finder.extWarning": .bool(false), "finder.path": .bool(true),
            "finder.status": .bool(true), "finder.titlePath": .bool(true), "finder.foldersFirst": .bool(true),
            "finder.search": .string("SCcf"), "finder.view": .string("Nlsv"), "finder.dsstore": .bool(true),
        ]),
    ]
}
