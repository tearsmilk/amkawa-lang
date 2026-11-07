import AppKit
import AVFoundation
import UniformTypeIdentifiers

/// Карточка видео в библиотеке: превью, имя, рамка у текущего.
final class VideoTile: NSView {
    let url: URL
    var isCurrent: Bool { didSet { updateLook() } }
    var onPick: (() -> Void)?
    var onRemove: (() -> Void)?
    var onReveal: (() -> Void)?

    private let thumb = CALayer()
    private let name: NSTextField
    private let missing: NSTextField
    private var hover = false { didSet { needsDisplay = true } }
    private var tracking: NSTrackingArea?
    private var menuActions: [Action] = []
    private let exists: Bool

    init(url: URL, current: Bool) {
        self.url = url
        self.isCurrent = current
        self.exists = FileManager.default.fileExists(atPath: url.path)
        name = Theme.label(url.deletingPathExtension().lastPathComponent, font: .systemFont(ofSize: 12.5, weight: .medium))
        missing = Theme.label("Файл не найден", font: .systemFont(ofSize: 12), color: Theme.muted)
        super.init(frame: .zero)
        wantsLayer = true
        toolTip = url.path
        thumb.contentsGravity = .resizeAspectFill
        thumb.masksToBounds = true
        thumb.cornerRadius = 8
        thumb.backgroundColor = NSColor.black.withAlphaComponent(0.85).cgColor
        layer?.addSublayer(thumb)
        name.translatesAutoresizingMaskIntoConstraints = true
        missing.translatesAutoresizingMaskIntoConstraints = true
        missing.alignment = .center
        missing.textColor = NSColor.white.withAlphaComponent(0.7)
        missing.isHidden = exists
        addSubview(name)
        addSubview(missing)
        updateLook()
        if exists {
            Thumbnails.shared.image(for: url) { [weak self] img in self?.thumb.contents = img }
        }
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) не используется") }

    private func updateLook() {
        name.textColor = isCurrent ? Theme.accent : (exists ? Theme.text : Theme.muted)
        needsDisplay = true
    }

    override var wantsUpdateLayer: Bool { true }

    override func updateLayer() {
        layer?.cornerRadius = 12
        layer?.backgroundColor = (hover ? Theme.panelHover : Theme.panel).cgColor
        layer?.borderWidth = isCurrent ? 2 : 1
        layer?.borderColor = (isCurrent ? Theme.accent : Theme.border).cgColor
    }

    override func layout() {
        super.layout()
        let pad: CGFloat = 8
        let thumbH = bounds.height - 34 - pad
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        thumb.frame = CGRect(x: pad, y: bounds.height - pad - thumbH, width: bounds.width - pad * 2, height: thumbH)
        CATransaction.commit()
        name.frame = NSRect(x: pad + 2, y: 8, width: bounds.width - pad * 2 - 4, height: 18)
        missing.frame = NSRect(x: pad, y: thumb.frame.midY - 9, width: bounds.width - pad * 2, height: 18)
    }

    override func updateTrackingAreas() {
        super.updateTrackingAreas()
        if let t = tracking { removeTrackingArea(t) }
        let t = NSTrackingArea(rect: .zero, options: [.mouseEnteredAndExited, .activeAlways, .inVisibleRect], owner: self)
        addTrackingArea(t)
        tracking = t
    }

    override func mouseEntered(with event: NSEvent) { hover = true; NSCursor.pointingHand.set() }
    override func mouseExited(with event: NSEvent) { hover = false; NSCursor.arrow.set() }
    override func mouseDown(with event: NSEvent) {}

    override func mouseUp(with event: NSEvent) {
        if bounds.contains(convert(event.locationInWindow, from: nil)) { onPick?() }
    }

    override func menu(for event: NSEvent) -> NSMenu? {
        menuActions.removeAll()
        let menu = NSMenu()
        func add(_ title: String, _ fn: (() -> Void)?) {
            let a = Action { _ in fn?() }
            menuActions.append(a)
            let item = NSMenuItem(title: title, action: #selector(Action.run(_:)), keyEquivalent: "")
            item.target = a
            menu.addItem(item)
        }
        if exists { add("Поставить обоями", onPick) }
        if exists { add("Показать в Finder", onReveal) }
        menu.addItem(.separator())
        add("Убрать из библиотеки", onRemove)
        return menu
    }
}

/// Сетка карточек + приём перетаскиваемых файлов.
final class GridView: NSView {
    private(set) var tiles: [VideoTile] = []
    var onDrop: (([URL]) -> Void)?

    private let empty = NSTextField(wrappingLabelWithString: "Перетащи сюда видео (.mp4, .mov, .m4v)\nили нажми «Добавить видео…»")
    private var dropHighlight = false { didSet { needsDisplay = true } }
    private var lastWidth: CGFloat = 600
    private var lastMinHeight: CGFloat = 400

    override init(frame: NSRect) {
        super.init(frame: frame)
        registerForDraggedTypes([.fileURL])
        empty.alignment = .center
        empty.font = .systemFont(ofSize: 14)
        empty.textColor = Theme.muted
        addSubview(empty)
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) не используется") }

    override var isFlipped: Bool { true }

    func setTiles(_ newTiles: [VideoTile]) {
        tiles.forEach { $0.removeFromSuperview() }
        tiles = newTiles
        newTiles.forEach { addSubview($0) }
        empty.isHidden = !newTiles.isEmpty
        fit(width: lastWidth, minHeight: lastMinHeight)
    }

    func fit(width: CGFloat, minHeight: CGFloat) {
        lastWidth = max(200, width)
        lastMinHeight = minHeight
        let gap: CGFloat = 14
        let cols = max(1, Int((lastWidth + gap) / (210 + gap)))
        let tileW = floor((lastWidth - gap * CGFloat(cols - 1)) / CGFloat(cols))
        let tileH = round((tileW - 16) * 9 / 16) + 42
        for (i, tile) in tiles.enumerated() {
            let row = i / cols, col = i % cols
            tile.frame = NSRect(x: CGFloat(col) * (tileW + gap), y: CGFloat(row) * (tileH + gap), width: tileW, height: tileH)
        }
        let rows = (tiles.count + cols - 1) / cols
        setFrameSize(NSSize(width: lastWidth, height: max(minHeight, CGFloat(rows) * (tileH + gap))))
        empty.frame = NSRect(x: 20, y: minHeight / 2 - 24, width: lastWidth - 40, height: 48)
        needsDisplay = true
    }

    override func draw(_ dirtyRect: NSRect) {
        guard tiles.isEmpty || dropHighlight else { return }
        let rect = NSRect(x: 1, y: 1, width: bounds.width - 2, height: max(0, lastMinHeight - 2))
        let path = NSBezierPath(roundedRect: rect, xRadius: 14, yRadius: 14)
        path.lineWidth = dropHighlight ? 2 : 1.5
        path.setLineDash([7, 5], count: 2, phase: 0)
        (dropHighlight ? Theme.accent : Theme.border).setStroke()
        if dropHighlight {
            Theme.accent.withAlphaComponent(0.06).setFill()
            path.fill()
        }
        path.stroke()
    }

    private func fileURLs(_ info: NSDraggingInfo) -> [URL] {
        info.draggingPasteboard.readObjects(forClasses: [NSURL.self], options: [.urlReadingFileURLsOnly: true]) as? [URL] ?? []
    }

    override func draggingEntered(_ sender: NSDraggingInfo) -> NSDragOperation {
        let ok = !fileURLs(sender).isEmpty
        dropHighlight = ok
        return ok ? .copy : []
    }

    override func draggingExited(_ sender: NSDraggingInfo?) { dropHighlight = false }

    override func performDragOperation(_ sender: NSDraggingInfo) -> Bool {
        dropHighlight = false
        let urls = fileURLs(sender)
        guard !urls.isEmpty else { return false }
        onDrop?(urls)
        return true
    }
}

/// Главное окно: библиотека видео слева, настройки справа.
final class LibraryWindowController: NSWindowController, NSWindowDelegate {
    let wallpaper: WallpaperController
    var settings: Settings { wallpaper.settings }
    var onClose: (() -> Void)?

    private var actions: [Action] = []
    private let grid = GridView(frame: NSRect(x: 0, y: 0, width: 600, height: 400))
    private let scroll = NSScrollView()
    private let nowLabel = Theme.label("", font: Theme.serif(17))
    private let stateLabel = Theme.label("", font: .systemFont(ofSize: 12), color: Theme.muted)
    private var pauseButton: NSButton!
    private var clearButton: NSButton!
    private var soundBox: NSButton!
    private var volumeSlider: NSSlider!
    private var loginBox: NSButton!

    var tileCount: Int { grid.tiles.count }

    init(wallpaper: WallpaperController) {
        self.wallpaper = wallpaper
        let win = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 940, height: 600),
                           styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
                           backing: .buffered, defer: false)
        win.title = "TnQkoWallpaper"
        win.titlebarAppearsTransparent = true
        win.titleVisibility = .hidden
        win.minSize = NSSize(width: 780, height: 500)
        win.isReleasedWhenClosed = false
        win.setFrameAutosaveName("TnQkoLibrary")
        super.init(window: win)
        win.delegate = self
        build()
        reload()
        if !win.setFrameUsingName("TnQkoLibrary") { win.center() }
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) не используется") }

    func windowWillClose(_ notification: Notification) { onClose?() }

    // MARK: построение

    private func act(_ fn: @escaping (Any?) -> Void) -> Action {
        let a = Action(fn)
        actions.append(a)
        return a
    }

    private func button(_ title: String, accent: Bool = false, _ fn: @escaping () -> Void) -> NSButton {
        let a = act { _ in fn() }
        let b = NSButton(title: title, target: a, action: #selector(Action.run(_:)))
        b.bezelStyle = .rounded
        if accent {
            b.bezelColor = Theme.accent
            b.contentTintColor = .white
        }
        b.translatesAutoresizingMaskIntoConstraints = false
        return b
    }

    private func checkbox(_ title: String, _ on: Bool, _ fn: @escaping (Bool) -> Void) -> NSButton {
        let a = act { sender in fn((sender as? NSButton)?.state == .on) }
        let b = NSButton(checkboxWithTitle: title, target: a, action: #selector(Action.run(_:)))
        b.state = on ? .on : .off
        b.translatesAutoresizingMaskIntoConstraints = false
        return b
    }

    private func popup(_ items: [String], selected: Int, _ fn: @escaping (Int) -> Void) -> NSPopUpButton {
        let a = act { sender in fn((sender as? NSPopUpButton)?.indexOfSelectedItem ?? 0) }
        let p = NSPopUpButton(frame: .zero, pullsDown: false)
        p.addItems(withTitles: items)
        p.selectItem(at: selected)
        p.target = a
        p.action = #selector(Action.run(_:))
        p.translatesAutoresizingMaskIntoConstraints = false
        return p
    }

    private func separator() -> NSView {
        let line = FillView(color: Theme.border)
        line.heightAnchor.constraint(equalToConstant: 1).isActive = true
        return line
    }

    private func build() {
        guard let win = window else { return }
        let root = FillView(color: Theme.background)
        root.translatesAutoresizingMaskIntoConstraints = true
        win.contentView = root

        // шапка
        let title = Theme.label("TnQkoWallpaper", font: Theme.serif(28))
        let subtitle = Theme.label("Живые обои из любого видео. Перетащи ролик в библиотеку и нажми на него.", color: Theme.muted)
        let titles = NSStackView(views: [title, subtitle])
        titles.orientation = .vertical
        titles.alignment = .leading
        titles.spacing = 4
        let add = button("Добавить видео…", accent: true) { [weak self] in self?.addVideos() }
        add.controlSize = .large
        let header = NSStackView(views: [titles, add])
        header.orientation = .horizontal
        header.distribution = .equalSpacing
        header.alignment = .centerY
        header.translatesAutoresizingMaskIntoConstraints = false
        titles.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        subtitle.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)

        // сетка
        scroll.translatesAutoresizingMaskIntoConstraints = false
        scroll.drawsBackground = false
        scroll.hasVerticalScroller = true
        scroll.autohidesScrollers = true
        scroll.borderType = .noBorder
        scroll.documentView = grid
        scroll.contentView.postsFrameChangedNotifications = true
        NotificationCenter.default.addObserver(self, selector: #selector(clipResized), name: NSView.frameDidChangeNotification, object: scroll.contentView)
        grid.onDrop = { [weak self] urls in self?.add(urls) }

        // панель настроек
        let side = FillView(color: Theme.panel, radius: 14)
        pauseButton = button("Пауза") { [weak self] in
            guard let self = self else { return }
            self.settings.paused.toggle()
            self.wallpaper.updatePlayback()
        }
        clearButton = button("Убрать обои") { [weak self] in self?.wallpaper.clear() }
        let controls = NSStackView(views: [pauseButton, clearButton])
        controls.spacing = 8

        soundBox = checkbox("Со звуком", settings.sound) { [weak self] on in
            self?.settings.sound = on
            self?.wallpaper.applyAudio()
            self?.refreshState()
        }
        let vol = act { [weak self] sender in
            self?.settings.volume = Float((sender as? NSSlider)?.doubleValue ?? 0.5)
            self?.wallpaper.applyAudio()
        }
        volumeSlider = NSSlider(value: Double(settings.volume), minValue: 0, maxValue: 1, target: vol, action: #selector(Action.run(_:)))
        volumeSlider.isContinuous = true
        volumeSlider.translatesAutoresizingMaskIntoConstraints = false
        let speakerLow = NSImageView(image: NSImage(systemSymbolName: "speaker.fill", accessibilityDescription: nil) ?? NSImage())
        let speakerHigh = NSImageView(image: NSImage(systemSymbolName: "speaker.wave.3.fill", accessibilityDescription: nil) ?? NSImage())
        speakerLow.contentTintColor = Theme.muted
        speakerHigh.contentTintColor = Theme.muted
        let volumeRow = NSStackView(views: [speakerLow, volumeSlider, speakerHigh])
        volumeRow.spacing = 6

        let fill = popup(FillMode.allCases.map { $0.title }, selected: FillMode.allCases.firstIndex(of: settings.fillMode) ?? 0) { [weak self] i in
            self?.settings.fillMode = FillMode.allCases[i]
            self?.wallpaper.applyFill()
        }
        let displays = popup(DisplayMode.allCases.map { $0.title }, selected: DisplayMode.allCases.firstIndex(of: settings.displayMode) ?? 0) { [weak self] i in
            self?.settings.displayMode = DisplayMode.allCases[i]
            self?.wallpaper.rebuildWindows()
        }

        let battery = checkbox("Пауза при работе от батареи", settings.pauseOnBattery) { [weak self] on in
            self?.settings.pauseOnBattery = on
            self?.wallpaper.updatePlayback()
        }
        let covered = checkbox("Пауза, когда окно на весь экран", settings.pauseWhenCovered) { [weak self] on in
            self?.settings.pauseWhenCovered = on
            self?.wallpaper.updatePlayback()
        }
        let still = checkbox("Кадр видео — обычными обоями", settings.staticWallpaper) { [weak self] on in
            self?.settings.staticWallpaper = on
        }
        still.toolTip = "Виден в Mission Control, на экране входа и после выхода из программы"
        loginBox = checkbox("Запускать при входе в систему", LoginItem.isEnabled) { [weak self] on in
            do {
                try LoginItem.setEnabled(on)
            } catch {
                self?.loginBox.state = on ? .off : .on
                let alert = NSAlert(error: error)
                alert.messageText = "Не удалось изменить автозапуск"
                if let w = self?.window { alert.beginSheetModal(for: w) }
            }
        }

        let views: [NSView] = [
            Theme.caption("Сейчас"), nowLabel, stateLabel, controls, separator(),
            Theme.caption("Звук"), soundBox, volumeRow, separator(),
            Theme.caption("Масштаб"), fill, Theme.caption("Экраны"), displays, separator(),
            Theme.caption("Экономия и система"), battery, covered, still, loginBox,
        ]
        let stack = NSStackView(views: views)
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 8
        stack.translatesAutoresizingMaskIntoConstraints = false
        for v in [nowLabel, stateLabel, volumeRow, fill, displays] {
            v.widthAnchor.constraint(equalTo: stack.widthAnchor).isActive = true
        }
        for v in views where v is FillView { v.widthAnchor.constraint(equalTo: stack.widthAnchor).isActive = true }
        stack.setCustomSpacing(14, after: controls)
        stack.setCustomSpacing(4, after: nowLabel)
        side.addSubview(stack)

        root.addSubview(header)
        root.addSubview(scroll)
        root.addSubview(side)
        NSLayoutConstraint.activate([
            header.topAnchor.constraint(equalTo: root.topAnchor, constant: 40),
            header.leadingAnchor.constraint(equalTo: root.leadingAnchor, constant: 28),
            header.trailingAnchor.constraint(equalTo: root.trailingAnchor, constant: -28),

            side.topAnchor.constraint(equalTo: header.bottomAnchor, constant: 20),
            side.trailingAnchor.constraint(equalTo: root.trailingAnchor, constant: -28),
            side.bottomAnchor.constraint(lessThanOrEqualTo: root.bottomAnchor, constant: -24),
            side.widthAnchor.constraint(equalToConstant: 290),

            stack.topAnchor.constraint(equalTo: side.topAnchor, constant: 18),
            stack.leadingAnchor.constraint(equalTo: side.leadingAnchor, constant: 18),
            stack.trailingAnchor.constraint(equalTo: side.trailingAnchor, constant: -18),
            stack.bottomAnchor.constraint(equalTo: side.bottomAnchor, constant: -18),

            scroll.topAnchor.constraint(equalTo: header.bottomAnchor, constant: 20),
            scroll.leadingAnchor.constraint(equalTo: root.leadingAnchor, constant: 28),
            scroll.trailingAnchor.constraint(equalTo: side.leadingAnchor, constant: -20),
            scroll.bottomAnchor.constraint(equalTo: root.bottomAnchor, constant: -24),
        ])
        refreshState()
    }

    @objc private func clipResized() {
        grid.fit(width: scroll.contentView.bounds.width, minHeight: scroll.contentView.bounds.height)
    }

    // MARK: данные

    func reload() {
        let current = wallpaper.currentURL?.standardizedFileURL.path
        let tiles = settings.library.map { url -> VideoTile in
            let tile = VideoTile(url: url, current: url.standardizedFileURL.path == current)
            tile.onPick = { [weak self] in self?.pick(url) }
            tile.onRemove = { [weak self] in self?.remove(url) }
            tile.onReveal = { NSWorkspace.shared.activateFileViewerSelecting([url]) }
            return tile
        }
        grid.setTiles(tiles)
        clipResized()
    }

    func refreshState() {
        let current = wallpaper.currentURL
        nowLabel.stringValue = current?.deletingPathExtension().lastPathComponent ?? "Обои не выбраны"
        if current == nil {
            stateLabel.stringValue = "Выбери видео в библиотеке"
        } else {
            let state = wallpaper.pauseReason?.rawValue ?? "Играет по кругу"
            stateLabel.stringValue = state + (settings.sound ? " · со звуком" : " · без звука")
        }
        pauseButton.title = settings.paused ? "Продолжить" : "Пауза"
        pauseButton.isEnabled = current != nil
        clearButton.isEnabled = current != nil
        soundBox.state = settings.sound ? .on : .off
        volumeSlider.isEnabled = settings.sound
        let path = current?.standardizedFileURL.path
        for tile in grid.tiles { tile.isCurrent = tile.url.standardizedFileURL.path == path }
    }

    private func pick(_ url: URL) {
        guard FileManager.default.fileExists(atPath: url.path) else { return }
        settings.paused = false
        wallpaper.setVideo(url)
        refreshState()
    }

    private func remove(_ url: URL) {
        if wallpaper.currentURL?.standardizedFileURL.path == url.standardizedFileURL.path { wallpaper.clear() }
        settings.removeFromLibrary(url)
        reload()
        refreshState()
    }

    private func addVideos() {
        guard let win = window else { return }
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = true
        panel.canChooseDirectories = false
        panel.allowedContentTypes = [.movie]
        panel.message = "Выбери видео для обоев"
        panel.prompt = "Добавить"
        panel.beginSheetModal(for: win) { [weak self] response in
            if response == .OK { self?.add(panel.urls) }
        }
    }

    /// Добавляет видео, которые macOS умеет проигрывать; первое добавленное сразу ставит обоями, если обоев ещё нет.
    func add(_ urls: [URL]) {
        var playable: [URL] = []
        var rejected: [String] = []
        for url in urls {
            if AVURLAsset(url: url).isPlayable { playable.append(url) } else { rejected.append(url.lastPathComponent) }
        }
        let added = settings.addToLibrary(playable)
        reload()
        if wallpaper.currentURL == nil, let first = added.first ?? playable.first { pick(first) }
        if !rejected.isEmpty, let win = window {
            let alert = NSAlert()
            alert.messageText = "macOS не умеет проигрывать эти файлы"
            alert.informativeText = rejected.joined(separator: ", ")
                + "\n\nПодходят .mp4 / .mov / .m4v (H.264 или HEVC). WebM и MKV сначала перекодируй, например в HandBrake."
            alert.beginSheetModal(for: win)
        }
    }
}
