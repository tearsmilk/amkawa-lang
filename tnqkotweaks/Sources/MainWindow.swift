import AppKit

/// Строка настройки: название, подсказка, пометка и контрол справа; «↺» — вернуть как в macOS.
final class TweakRow: NSView {
    let tweak: Tweak
    private var actions: [Action] = []
    private var control: NSView!
    private var valueLabel: NSTextField?
    private let resetButton: NSButton
    private let changedDot = FillView(color: Theme.accent, radius: 3)

    init(_ t: Tweak) {
        tweak = t
        resetButton = NSButton(title: "", target: nil, action: nil)
        super.init(frame: .zero)
        translatesAutoresizingMaskIntoConstraints = false

        let title = Theme.label(t.title, font: .systemFont(ofSize: 13.5, weight: .medium))
        var texts: [NSView] = [title]
        if !t.hint.isEmpty { texts.append(Theme.label(t.hint, font: .systemFont(ofSize: 11.5), color: Theme.muted)) }
        if let n = t.note { texts.append(Theme.label("ⓘ " + n, font: .systemFont(ofSize: 11), color: Theme.accent)) }
        let textStack = NSStackView(views: texts)
        textStack.orientation = .vertical
        textStack.alignment = .leading
        textStack.spacing = 2
        textStack.translatesAutoresizingMaskIntoConstraints = false

        control = makeControl()
        control.translatesAutoresizingMaskIntoConstraints = false

        let resetAction = Action { [weak self] _ in
            guard let self = self else { return }
            Engine.shared.reset(self.tweak)
            self.refresh()
        }
        actions.append(resetAction)
        resetButton.image = NSImage(systemSymbolName: "arrow.counterclockwise", accessibilityDescription: "Как в macOS")
        resetButton.isBordered = false
        resetButton.contentTintColor = Theme.muted
        resetButton.toolTip = "Вернуть как в macOS"
        resetButton.target = resetAction
        resetButton.action = #selector(Action.run(_:))
        resetButton.translatesAutoresizingMaskIntoConstraints = false

        addSubview(changedDot)
        addSubview(textStack)
        addSubview(control)
        addSubview(resetButton)
        NSLayoutConstraint.activate([
            changedDot.widthAnchor.constraint(equalToConstant: 6),
            changedDot.heightAnchor.constraint(equalToConstant: 6),
            changedDot.leadingAnchor.constraint(equalTo: leadingAnchor),
            changedDot.centerYAnchor.constraint(equalTo: title.centerYAnchor),
            textStack.leadingAnchor.constraint(equalTo: leadingAnchor, constant: 14),
            textStack.topAnchor.constraint(equalTo: topAnchor, constant: 10),
            textStack.bottomAnchor.constraint(lessThanOrEqualTo: bottomAnchor, constant: -10),
            textStack.trailingAnchor.constraint(lessThanOrEqualTo: control.leadingAnchor, constant: -16),
            resetButton.trailingAnchor.constraint(equalTo: trailingAnchor),
            resetButton.centerYAnchor.constraint(equalTo: centerYAnchor),
            resetButton.widthAnchor.constraint(equalToConstant: 22),
            control.trailingAnchor.constraint(equalTo: resetButton.leadingAnchor, constant: -10),
            control.centerYAnchor.constraint(equalTo: centerYAnchor),
            heightAnchor.constraint(greaterThanOrEqualToConstant: 46),
            heightAnchor.constraint(greaterThanOrEqualTo: textStack.heightAnchor, constant: 20),
        ])
        control.setContentCompressionResistancePriority(.required, for: .horizontal)
        refresh()
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) не используется") }

    private func makeControl() -> NSView {
        let t = tweak
        switch t.kind {
        case .toggle(let inverted):
            let a = Action { [weak self] s in
                guard let self = self, let sw = s as? NSSwitch else { return }
                let on = sw.state == .on
                Engine.shared.set(t, .bool(inverted ? !on : on))
                self.refresh()
            }
            actions.append(a)
            let sw = NSSwitch()
            sw.target = a
            sw.action = #selector(Action.run(_:))
            return sw
        case .slider(let min, let max, let step, let unit, let integer):
            let label = Theme.label("", font: NSFont.monospacedDigitSystemFont(ofSize: 12, weight: .medium), color: Theme.muted)
            label.alignment = .right
            label.widthAnchor.constraint(equalToConstant: 64).isActive = true
            valueLabel = label
            let a = Action { [weak self] s in
                guard let self = self, let sl = s as? NSSlider else { return }
                let v = (sl.doubleValue / step).rounded() * step
                label.stringValue = TweakRow.format(v, unit: unit, integer: integer)
                // пишем только когда кнопку мыши отпустили — меньше перезапусков Dock
                if NSApp.currentEvent?.type == .leftMouseUp || NSApp.currentEvent?.type == .keyDown || NSApp.currentEvent == nil {
                    Engine.shared.set(t, integer ? .int(Int(v)) : .double(v))
                    self.refreshDot()
                }
            }
            actions.append(a)
            let sl = NSSlider(value: min, minValue: min, maxValue: max, target: a, action: #selector(Action.run(_:)))
            sl.isContinuous = true
            sl.widthAnchor.constraint(equalToConstant: 200).isActive = true
            let row = NSStackView(views: [sl, label])
            row.spacing = 8
            return row
        case .choice(let choices):
            let a = Action { [weak self] s in
                guard let self = self, let p = s as? NSPopUpButton, choices.indices.contains(p.indexOfSelectedItem) else { return }
                Engine.shared.set(t, choices[p.indexOfSelectedItem].value)
                self.refresh()
            }
            actions.append(a)
            let p = NSPopUpButton(frame: .zero, pullsDown: false)
            p.addItems(withTitles: choices.map { $0.title })
            p.target = a
            p.action = #selector(Action.run(_:))
            p.widthAnchor.constraint(greaterThanOrEqualToConstant: 190).isActive = true
            return p
        }
    }

    static func format(_ v: Double, unit: String, integer: Bool) -> String {
        let n = integer ? String(Int(v.rounded())) : String(format: v < 0.1 && v > 0 ? "%.3f" : "%.2f", v)
        return unit.isEmpty ? n : "\(n) \(unit)"
    }

    private func refreshDot() {
        changedDot.isHidden = !Engine.shared.isChanged(tweak)
        resetButton.isEnabled = !changedDot.isHidden
    }

    /// Перечитывает текущее значение из системы.
    func refresh() {
        let v = Engine.shared.current(tweak)
        switch tweak.kind {
        case .toggle(let inverted):
            (control as? NSSwitch)?.state = (inverted ? !v.bool : v.bool) ? .on : .off
        case .slider(_, _, _, let unit, let integer):
            if let row = control as? NSStackView, let sl = row.arrangedSubviews.first as? NSSlider {
                sl.doubleValue = v.double
                valueLabel?.stringValue = TweakRow.format(v.double, unit: unit, integer: integer)
            }
        case .choice(let choices):
            if let p = control as? NSPopUpButton {
                if let i = choices.firstIndex(where: { $0.value == v }) {
                    p.selectItem(at: i)
                } else {
                    p.select(nil)
                    p.setTitle("Своё значение")
                }
            }
        }
        refreshDot()
    }
}

/// Пункт бокового списка.
final class SidebarCell: NSTableCellView {
    let icon = NSImageView()
    let title = Theme.label("", font: .systemFont(ofSize: 13, weight: .medium))

    override init(frame: NSRect) {
        super.init(frame: frame)
        icon.translatesAutoresizingMaskIntoConstraints = false
        icon.contentTintColor = Theme.accent
        addSubview(icon)
        addSubview(title)
        NSLayoutConstraint.activate([
            icon.leadingAnchor.constraint(equalTo: leadingAnchor, constant: 10),
            icon.centerYAnchor.constraint(equalTo: centerYAnchor),
            icon.widthAnchor.constraint(equalToConstant: 18),
            title.leadingAnchor.constraint(equalTo: icon.trailingAnchor, constant: 9),
            title.trailingAnchor.constraint(lessThanOrEqualTo: trailingAnchor, constant: -8),
            title.centerYAnchor.constraint(equalTo: centerYAnchor),
        ])
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) не используется") }
}

final class MainWindowController: NSWindowController, NSWindowDelegate, NSTableViewDataSource, NSTableViewDelegate {
    struct Page {
        let title: String
        let symbol: String
        let subtitle: String
        let section: Section?
    }

    let pages: [Page]
    private let sidebar = NSTableView()
    private let pageTitle = Theme.label("", font: Theme.serif(26))
    private let pageSubtitle = Theme.label("", font: .systemFont(ofSize: 13), color: Theme.muted)
    private let scroll = NSScrollView()
    private let content = FlippedView()
    private var rows: [TweakRow] = []
    private var actions: [Action] = []
    var onClose: (() -> Void)?

    init() {
        pages = [Page(title: "Пресеты", symbol: "sparkles", subtitle: "Готовые наборы и откат всех изменений", section: nil)]
            + Catalog.sections.map { Page(title: $0.title, symbol: $0.symbol, subtitle: $0.subtitle, section: $0) }
            + [Page(title: "Виджеты", symbol: "gauge", subtitle: "Процессор, память и сеть в строке меню — по желанию", section: nil)]
        let win = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 940, height: 640),
                           styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
                           backing: .buffered, defer: false)
        win.title = "TnQkoTweaks"
        win.titlebarAppearsTransparent = true
        win.titleVisibility = .hidden
        win.minSize = NSSize(width: 820, height: 520)
        win.isReleasedWhenClosed = false
        win.setFrameAutosaveName("TnQkoTweaksMain")
        super.init(window: win)
        win.delegate = self
        build()
        if !win.setFrameUsingName("TnQkoTweaksMain") { win.center() }
        sidebar.selectRowIndexes(IndexSet(integer: 1), byExtendingSelection: false)
        show(page: 1)
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) не используется") }

    func windowWillClose(_ notification: Notification) { onClose?() }

    /// Значения могли поменять в Системных настройках — перечитываем при возвращении в окно.
    func windowDidBecomeKey(_ notification: Notification) { rows.forEach { $0.refresh() } }

    var rowCount: Int { rows.count }

    private func build() {
        guard let win = window else { return }
        let root = FillView(color: Theme.background)
        root.translatesAutoresizingMaskIntoConstraints = true
        win.contentView = root

        let side = FillView(color: Theme.panel)
        let brand = Theme.label("TnQkoTweaks", font: Theme.serif(20))
        let brandSub = Theme.label("Настройки macOS без нагрузки", font: .systemFont(ofSize: 11.5), color: Theme.muted)
        let column = NSTableColumn(identifier: NSUserInterfaceItemIdentifier("page"))
        column.resizingMask = .autoresizingMask
        sidebar.addTableColumn(column)
        sidebar.columnAutoresizingStyle = .firstColumnOnlyAutoresizingStyle
        sidebar.headerView = nil
        sidebar.rowHeight = 34
        sidebar.backgroundColor = .clear
        sidebar.style = .sourceList
        sidebar.dataSource = self
        sidebar.delegate = self
        let sideScroll = NSScrollView()
        sideScroll.documentView = sidebar
        sideScroll.drawsBackground = false
        sideScroll.translatesAutoresizingMaskIntoConstraints = false
        side.addSubview(brand)
        side.addSubview(brandSub)
        side.addSubview(sideScroll)

        scroll.translatesAutoresizingMaskIntoConstraints = false
        scroll.drawsBackground = false
        scroll.hasVerticalScroller = true
        scroll.autohidesScrollers = true
        scroll.documentView = content
        content.translatesAutoresizingMaskIntoConstraints = false

        root.addSubview(side)
        root.addSubview(pageTitle)
        root.addSubview(pageSubtitle)
        root.addSubview(scroll)
        NSLayoutConstraint.activate([
            side.leadingAnchor.constraint(equalTo: root.leadingAnchor),
            side.topAnchor.constraint(equalTo: root.topAnchor),
            side.bottomAnchor.constraint(equalTo: root.bottomAnchor),
            side.widthAnchor.constraint(equalToConstant: 220),
            brand.topAnchor.constraint(equalTo: side.topAnchor, constant: 44),
            brand.leadingAnchor.constraint(equalTo: side.leadingAnchor, constant: 20),
            brandSub.topAnchor.constraint(equalTo: brand.bottomAnchor, constant: 2),
            brandSub.leadingAnchor.constraint(equalTo: brand.leadingAnchor),
            brandSub.trailingAnchor.constraint(lessThanOrEqualTo: side.trailingAnchor, constant: -12),
            sideScroll.topAnchor.constraint(equalTo: brandSub.bottomAnchor, constant: 16),
            sideScroll.leadingAnchor.constraint(equalTo: side.leadingAnchor, constant: 8),
            sideScroll.trailingAnchor.constraint(equalTo: side.trailingAnchor, constant: -8),
            sideScroll.bottomAnchor.constraint(equalTo: side.bottomAnchor, constant: -12),

            pageTitle.topAnchor.constraint(equalTo: root.topAnchor, constant: 40),
            pageTitle.leadingAnchor.constraint(equalTo: side.trailingAnchor, constant: 32),
            pageTitle.trailingAnchor.constraint(lessThanOrEqualTo: root.trailingAnchor, constant: -32),
            pageSubtitle.topAnchor.constraint(equalTo: pageTitle.bottomAnchor, constant: 4),
            pageSubtitle.leadingAnchor.constraint(equalTo: pageTitle.leadingAnchor),
            pageSubtitle.trailingAnchor.constraint(lessThanOrEqualTo: root.trailingAnchor, constant: -32),
            scroll.topAnchor.constraint(equalTo: pageSubtitle.bottomAnchor, constant: 16),
            scroll.leadingAnchor.constraint(equalTo: side.trailingAnchor, constant: 20),
            scroll.trailingAnchor.constraint(equalTo: root.trailingAnchor),
            scroll.bottomAnchor.constraint(equalTo: root.bottomAnchor),
            content.leadingAnchor.constraint(equalTo: scroll.contentView.leadingAnchor),
            content.trailingAnchor.constraint(equalTo: scroll.contentView.trailingAnchor),
            content.topAnchor.constraint(equalTo: scroll.contentView.topAnchor),
        ])
    }

    // MARK: боковой список

    func numberOfRows(in tableView: NSTableView) -> Int { pages.count }

    func tableView(_ tableView: NSTableView, viewFor tableColumn: NSTableColumn?, row: Int) -> NSView? {
        let id = NSUserInterfaceItemIdentifier("side")
        let cell = tableView.makeView(withIdentifier: id, owner: self) as? SidebarCell ?? {
            let c = SidebarCell(frame: .zero)
            c.identifier = id
            return c
        }()
        cell.title.stringValue = pages[row].title
        cell.icon.image = NSImage(systemSymbolName: pages[row].symbol, accessibilityDescription: nil)
        return cell
    }

    func tableViewSelectionDidChange(_ notification: Notification) {
        if sidebar.selectedRow >= 0 { show(page: sidebar.selectedRow) }
    }

    // MARK: страницы

    func show(page index: Int) {
        let page = pages[index]
        pageTitle.stringValue = page.title
        pageSubtitle.stringValue = page.subtitle
        content.subviews.forEach { $0.removeFromSuperview() }
        rows.removeAll()
        actions.removeAll()

        var views: [NSView] = []
        if let section = page.section {
            for (i, t) in section.tweaks.enumerated() {
                let row = TweakRow(t)
                rows.append(row)
                views.append(row)
                if i < section.tweaks.count - 1 { views.append(separator()) }
            }
            if section.id == "dock" {
                views.append(spacer(12))
                views.append(buttonRow([("Добавить разделитель в Dock", { SystemActions.addDockSpacer() }),
                                        ("Перезапустить Dock", { Engine.shared.scheduleRestart(["Dock"]) })]))
            }
            if section.id == "finder" {
                views.append(spacer(12))
                views.append(buttonRow([("Перезапустить Finder", { Engine.shared.scheduleRestart(["Finder"]) })]))
            }
        } else if page.title == "Пресеты" {
            views = presetViews()
        } else {
            views = widgetViews()
        }
        let stack = NSStackView(views: views)
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 0
        stack.translatesAutoresizingMaskIntoConstraints = false
        content.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.topAnchor.constraint(equalTo: content.topAnchor, constant: 4),
            stack.leadingAnchor.constraint(equalTo: content.leadingAnchor, constant: 12),
            stack.trailingAnchor.constraint(equalTo: content.trailingAnchor, constant: -32),
            stack.bottomAnchor.constraint(equalTo: content.bottomAnchor, constant: -28),
        ])
        for v in views { v.widthAnchor.constraint(equalTo: stack.widthAnchor).isActive = true }
        scroll.contentView.scroll(to: .zero)
    }

    private func separator() -> NSView {
        let v = FillView(color: Theme.border)
        v.heightAnchor.constraint(equalToConstant: 1).isActive = true
        return v
    }

    private func spacer(_ h: CGFloat) -> NSView {
        let v = NSView()
        v.translatesAutoresizingMaskIntoConstraints = false
        v.heightAnchor.constraint(equalToConstant: h).isActive = true
        return v
    }

    private func button(_ title: String, accent: Bool = false, _ fn: @escaping () -> Void) -> NSButton {
        let a = Action { _ in fn() }
        actions.append(a)
        let b = NSButton(title: title, target: a, action: #selector(Action.run(_:)))
        b.bezelStyle = .rounded
        if accent {
            b.bezelColor = Theme.accent
            b.contentTintColor = .white
        }
        return b
    }

    private func buttonRow(_ items: [(String, () -> Void)]) -> NSView {
        let row = NSStackView(views: items.map { button($0.0, $0.1) })
        row.spacing = 8
        row.alignment = .leading
        let wrap = NSStackView(views: [row, NSView()])
        wrap.orientation = .horizontal
        return wrap
    }

    private func card(_ title: String, _ text: String, _ button: NSButton) -> NSView {
        let card = FillView(color: Theme.panel, radius: 12)
        let t = Theme.label(title, font: Theme.serif(17))
        let d = NSTextField(wrappingLabelWithString: text)
        d.font = .systemFont(ofSize: 12.5)
        d.textColor = Theme.muted
        d.translatesAutoresizingMaskIntoConstraints = false
        d.setContentCompressionResistancePriority(NSLayoutConstraint.Priority(250), for: .horizontal)
        button.translatesAutoresizingMaskIntoConstraints = false
        card.addSubview(t)
        card.addSubview(d)
        card.addSubview(button)
        NSLayoutConstraint.activate([
            t.topAnchor.constraint(equalTo: card.topAnchor, constant: 14),
            t.leadingAnchor.constraint(equalTo: card.leadingAnchor, constant: 16),
            d.topAnchor.constraint(equalTo: t.bottomAnchor, constant: 4),
            d.leadingAnchor.constraint(equalTo: t.leadingAnchor),
            d.trailingAnchor.constraint(equalTo: button.leadingAnchor, constant: -16),
            d.bottomAnchor.constraint(equalTo: card.bottomAnchor, constant: -14),
            button.trailingAnchor.constraint(equalTo: card.trailingAnchor, constant: -16),
            button.centerYAnchor.constraint(equalTo: card.centerYAnchor),
        ])
        button.setContentCompressionResistancePriority(.required, for: .horizontal)
        let wrap = NSStackView(views: [card])
        wrap.edgeInsets = NSEdgeInsets(top: 0, left: 0, bottom: 10, right: 0)
        card.widthAnchor.constraint(equalTo: wrap.widthAnchor).isActive = true
        return wrap
    }

    private func presetViews() -> [NSView] {
        var views: [NSView] = []
        for p in Catalog.presets {
            views.append(card(p.title, p.hint, button("Применить", accent: true) {
                Engine.shared.applyPreset(p.values)
            }))
        }
        views.append(card("Вернуть как было", "Все настройки, которые меняла программа, вернутся к значениям до её первого запуска.",
                          button("Вернуть") { [weak self] in self?.confirm("Вернуть все изменения?") { Engine.shared.restoreBackup() } }))
        views.append(card("Стандартные настройки macOS", "Сбросить всё, что есть в программе, к заводским значениям macOS.",
                          button("Сбросить") { [weak self] in
                              self?.confirm("Сбросить всё к стандартным значениям macOS?") { Catalog.all.forEach { Engine.shared.reset($0) } }
                          }))
        let note = NSTextField(wrappingLabelWithString: "Программа меняет системные параметры один раз и может быть закрыта — настройки останутся, а процессор и батарея не тратятся. Dock, Finder и строка меню перезапускаются на секунду, чтобы подхватить изменения.")
        note.font = .systemFont(ofSize: 12)
        note.textColor = Theme.muted
        views.append(note)
        return views
    }

    private func widgetViews() -> [NSView] {
        let w = Widgets.shared
        func toggle(_ title: String, _ hint: String, _ on: Bool, _ set: @escaping (Bool) -> Void) -> NSView {
            let a = Action { s in set((s as? NSSwitch)?.state == .on) }
            actions.append(a)
            let sw = NSSwitch()
            sw.state = on ? .on : .off
            sw.target = a
            sw.action = #selector(Action.run(_:))
            return simpleRow(title, hint, sw)
        }
        let intervals: [Double] = [1, 2, 5, 10]
        let ia = Action { s in
            if let p = s as? NSPopUpButton { w.interval = intervals[max(0, p.indexOfSelectedItem)] }
        }
        actions.append(ia)
        let pop = NSPopUpButton(frame: .zero, pullsDown: false)
        pop.addItems(withTitles: ["Каждую секунду", "Каждые 2 секунды", "Каждые 5 секунд", "Каждые 10 секунд"])
        pop.selectItem(at: intervals.firstIndex(of: w.interval) ?? 1)
        pop.target = ia
        pop.action = #selector(Action.run(_:))
        let note = NSTextField(wrappingLabelWithString: "Один пункт в строке меню. Считается раз в несколько секунд и замирает, пока экран спит; когда все счётчики выключены — не работает вовсе. Чтобы счётчики жили после закрытия окна, программа остаётся в строке меню.")
        note.font = .systemFont(ofSize: 12)
        note.textColor = Theme.muted
        return [
            toggle("Загрузка процессора", "CPU 12%", w.showCPU) { w.showCPU = $0 },
            separator(),
            toggle("Память", "RAM 7.9/16 ГБ", w.showRAM) { w.showRAM = $0 },
            separator(),
            toggle("Сеть", "↓1.2 МБ/с ↑40 КБ/с", w.showNet) { w.showNet = $0 },
            separator(),
            simpleRow("Как часто обновлять", "Реже — ещё меньше нагрузки", pop),
            separator(),
            toggle("Запускать при входе в систему", "Только счётчики в строке меню, без окна", LoginItem.isEnabled) { on in try? LoginItem.setEnabled(on) },
            spacer(14),
            note,
        ]
    }

    private func simpleRow(_ title: String, _ hint: String, _ control: NSView) -> NSView {
        let v = NSView()
        v.translatesAutoresizingMaskIntoConstraints = false
        let t = Theme.label(title, font: .systemFont(ofSize: 13.5, weight: .medium))
        let h = Theme.label(hint, font: .systemFont(ofSize: 11.5), color: Theme.muted)
        control.translatesAutoresizingMaskIntoConstraints = false
        v.addSubview(t)
        v.addSubview(h)
        v.addSubview(control)
        NSLayoutConstraint.activate([
            t.leadingAnchor.constraint(equalTo: v.leadingAnchor, constant: 14),
            t.topAnchor.constraint(equalTo: v.topAnchor, constant: 10),
            h.leadingAnchor.constraint(equalTo: t.leadingAnchor),
            h.topAnchor.constraint(equalTo: t.bottomAnchor, constant: 2),
            h.bottomAnchor.constraint(equalTo: v.bottomAnchor, constant: -10),
            h.trailingAnchor.constraint(lessThanOrEqualTo: control.leadingAnchor, constant: -16),
            control.trailingAnchor.constraint(equalTo: v.trailingAnchor, constant: -32),
            control.centerYAnchor.constraint(equalTo: v.centerYAnchor),
        ])
        return v
    }

    private func confirm(_ text: String, _ fn: @escaping () -> Void) {
        guard let win = window else { return }
        let alert = NSAlert()
        alert.messageText = text
        alert.addButton(withTitle: "Да")
        alert.addButton(withTitle: "Отмена")
        alert.beginSheetModal(for: win) { [weak self] r in
            guard r == .alertFirstButtonReturn else { return }
            fn()
            self?.rows.forEach { $0.refresh() }
        }
    }
}

final class FlippedView: NSView {
    override var isFlipped: Bool { true }
}
