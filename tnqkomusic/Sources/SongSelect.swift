import AppKit
import AVFoundation
import UniformTypeIdentifiers

protocol SongSelectDelegate: AnyObject {
    func songSelect(play map: Beatmap)
}

/// Строка списка: название, исполнитель и сложность, «звёзды».
final class SongRow: NSTableCellView {
    let title = Theme.label("", font: .systemFont(ofSize: 14, weight: .semibold))
    let sub = Theme.label("", font: .systemFont(ofSize: 12), color: Theme.muted)
    let stars = Theme.label("", font: Theme.rounded(12, .semibold), color: Theme.accent)

    override init(frame: NSRect) {
        super.init(frame: frame)
        addSubview(title)
        addSubview(sub)
        addSubview(stars)
        stars.alignment = .right
        NSLayoutConstraint.activate([
            title.leadingAnchor.constraint(equalTo: leadingAnchor, constant: 14),
            title.topAnchor.constraint(equalTo: topAnchor, constant: 9),
            title.trailingAnchor.constraint(lessThanOrEqualTo: stars.leadingAnchor, constant: -8),
            sub.leadingAnchor.constraint(equalTo: title.leadingAnchor),
            sub.topAnchor.constraint(equalTo: title.bottomAnchor, constant: 3),
            sub.trailingAnchor.constraint(equalTo: trailingAnchor, constant: -14),
            stars.trailingAnchor.constraint(equalTo: trailingAnchor, constant: -14),
            stars.centerYAnchor.constraint(equalTo: title.centerYAnchor),
        ])
        stars.setContentCompressionResistancePriority(.required, for: .horizontal)
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) не используется") }
}

final class SongRowView: NSTableRowView {
    override func drawSelection(in dirtyRect: NSRect) {
        let r = bounds.insetBy(dx: 6, dy: 3)
        Theme.selection.setFill()
        NSBezierPath(roundedRect: r, xRadius: 10, yRadius: 10).fill()
        Theme.accent.setFill()
        NSBezierPath(roundedRect: NSRect(x: r.minX, y: r.minY + 8, width: 3, height: r.height - 16), xRadius: 1.5, yRadius: 1.5).fill()
    }
}

/// Главный экран: список карт, подробности, импорт, настройки.
final class SongSelectView: NSView, NSTableViewDataSource, NSTableViewDelegate {
    let library: Library
    let settings: Settings
    weak var delegate: SongSelectDelegate?

    private var filtered: [Beatmap] = []
    private let table = NSTableView()
    private let scroll = NSScrollView()
    private let search = NSSearchField()
    private let cover = NSImageView()
    private let titleLabel = Theme.label("", font: Theme.serif(28))
    private let artistLabel = Theme.label("", font: .systemFont(ofSize: 15), color: Theme.muted)
    private let versionLabel = Theme.label("", font: .systemFont(ofSize: 13, weight: .semibold), color: Theme.accent)
    private let statsLabel = Theme.label("", font: .systemFont(ofSize: 12.5), color: Theme.muted)
    private let bestLabel = Theme.label("", font: .systemFont(ofSize: 13), color: Theme.text)
    private let empty = NSTextField(wrappingLabelWithString: "")
    private var playButton: PillButton!
    private var deleteButton: PillButton!
    private let busy = FillView(color: NSColor.black.withAlphaComponent(0.6))
    private let busyLabel = Theme.label("", font: Theme.serif(20))
    private var preview: AVAudioPlayer?
    private var previewURL: URL?
    private var actions: [Action] = []

    init(library: Library, settings: Settings) {
        self.library = library
        self.settings = settings
        super.init(frame: NSRect(x: 0, y: 0, width: 1280, height: 800))
        wantsLayer = true
        registerForDraggedTypes([.fileURL])
        build()
        reload()
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) не используется") }

    override var wantsUpdateLayer: Bool { true }
    override func updateLayer() { layer?.backgroundColor = Theme.background.cgColor }

    var mapCount: Int { filtered.count }

    // MARK: построение

    private func build() {
        let title = Theme.label("TnQkoMusically", font: Theme.serif(30))
        let subtitle = Theme.label("Кликай по кружкам в ритм. Свои треки и карты osu! (.osz, .osu).", color: Theme.muted)
        let titles = NSStackView(views: [title, subtitle])
        titles.orientation = .vertical
        titles.alignment = .leading
        titles.spacing = 3

        let addTrack = PillButton("Добавить трек…") { [weak self] in self?.pickFiles(audio: true) }
        let addMap = PillButton("Импорт карты…", accent: false) { [weak self] in self?.pickFiles(audio: false) }
        let prefs = PillButton("Настройки", accent: false) { [weak self] in self?.showSettings() }
        let buttons = NSStackView(views: [addTrack, addMap, prefs])
        buttons.spacing = 10
        let header = NSStackView(views: [titles, buttons])
        header.distribution = .equalSpacing
        header.alignment = .centerY
        header.translatesAutoresizingMaskIntoConstraints = false

        search.placeholderString = "Поиск по названию, исполнителю, сложности"
        search.translatesAutoresizingMaskIntoConstraints = false
        let searchAction = Action { [weak self] _ in self?.applyFilter() }
        actions.append(searchAction)
        search.target = searchAction
        search.action = #selector(Action.run(_:))
        search.sendsSearchStringImmediately = true

        let column = NSTableColumn(identifier: NSUserInterfaceItemIdentifier("song"))
        table.addTableColumn(column)
        table.headerView = nil
        table.rowHeight = 56
        table.intercellSpacing = NSSize(width: 0, height: 0)
        table.backgroundColor = .clear
        table.selectionHighlightStyle = .regular
        table.dataSource = self
        table.delegate = self
        table.doubleAction = #selector(doubleClicked)
        table.target = self
        table.style = .plain
        scroll.documentView = table
        scroll.drawsBackground = false
        scroll.hasVerticalScroller = true
        scroll.autohidesScrollers = true
        scroll.translatesAutoresizingMaskIntoConstraints = false

        let listPanel = FillView(color: Theme.panel, radius: 16)
        listPanel.addSubview(search)
        listPanel.addSubview(scroll)
        empty.alignment = .center
        empty.textColor = Theme.muted
        empty.font = .systemFont(ofSize: 14)
        empty.translatesAutoresizingMaskIntoConstraints = false
        listPanel.addSubview(empty)

        // подробности
        let detail = FillView(color: Theme.panel, radius: 16)
        cover.imageScaling = .scaleProportionallyUpOrDown
        cover.wantsLayer = true
        cover.layer?.cornerRadius = 12
        cover.layer?.masksToBounds = true
        cover.layer?.backgroundColor = Theme.panelHover.cgColor
        cover.translatesAutoresizingMaskIntoConstraints = false
        playButton = PillButton("Играть") { [weak self] in self?.playSelected() }
        deleteButton = PillButton("Удалить", accent: false) { [weak self] in self?.deleteSelected() }
        let finder = PillButton("В Finder", accent: false) { [weak self] in
            if let f = self?.selected?.fileURL { NSWorkspace.shared.activateFileViewerSelecting([f]) }
        }
        let row = NSStackView(views: [playButton, finder, deleteButton])
        row.spacing = 10
        let hint = Theme.label("Клавиши Z / X или кнопки мыши · Esc — пауза · Пробел — пропуск вступления", font: .systemFont(ofSize: 11.5), color: Theme.muted)
        let info = NSStackView(views: [titleLabel, artistLabel, versionLabel, statsLabel, bestLabel, row, hint])
        info.orientation = .vertical
        info.alignment = .leading
        info.spacing = 6
        info.setCustomSpacing(14, after: bestLabel)
        info.setCustomSpacing(12, after: row)
        info.translatesAutoresizingMaskIntoConstraints = false
        detail.addSubview(cover)
        detail.addSubview(info)
        playButton.widthAnchor.constraint(greaterThanOrEqualToConstant: 160).isActive = true
        statsLabel.lineBreakMode = .byWordWrapping
        statsLabel.cell?.wraps = true
        statsLabel.maximumNumberOfLines = 2

        addSubview(header)
        addSubview(listPanel)
        addSubview(detail)

        busy.translatesAutoresizingMaskIntoConstraints = true
        busy.autoresizingMask = [.width, .height]
        busy.isHidden = true
        let spinner = NSProgressIndicator()
        spinner.style = .spinning
        spinner.startAnimation(nil)
        spinner.translatesAutoresizingMaskIntoConstraints = false
        let busyStack = NSStackView(views: [spinner, busyLabel])
        busyStack.orientation = .vertical
        busyStack.spacing = 14
        busyStack.translatesAutoresizingMaskIntoConstraints = false
        busy.addSubview(busyStack)
        addSubview(busy)

        NSLayoutConstraint.activate([
            header.topAnchor.constraint(equalTo: topAnchor, constant: 40),
            header.leadingAnchor.constraint(equalTo: leadingAnchor, constant: 28),
            header.trailingAnchor.constraint(equalTo: trailingAnchor, constant: -28),

            listPanel.topAnchor.constraint(equalTo: header.bottomAnchor, constant: 22),
            listPanel.leadingAnchor.constraint(equalTo: leadingAnchor, constant: 28),
            listPanel.bottomAnchor.constraint(equalTo: bottomAnchor, constant: -28),
            listPanel.widthAnchor.constraint(equalTo: widthAnchor, multiplier: 0.44),

            search.topAnchor.constraint(equalTo: listPanel.topAnchor, constant: 14),
            search.leadingAnchor.constraint(equalTo: listPanel.leadingAnchor, constant: 14),
            search.trailingAnchor.constraint(equalTo: listPanel.trailingAnchor, constant: -14),
            scroll.topAnchor.constraint(equalTo: search.bottomAnchor, constant: 10),
            scroll.leadingAnchor.constraint(equalTo: listPanel.leadingAnchor, constant: 4),
            scroll.trailingAnchor.constraint(equalTo: listPanel.trailingAnchor, constant: -4),
            scroll.bottomAnchor.constraint(equalTo: listPanel.bottomAnchor, constant: -8),
            empty.centerYAnchor.constraint(equalTo: scroll.centerYAnchor),
            empty.leadingAnchor.constraint(equalTo: listPanel.leadingAnchor, constant: 30),
            empty.trailingAnchor.constraint(equalTo: listPanel.trailingAnchor, constant: -30),

            detail.topAnchor.constraint(equalTo: listPanel.topAnchor),
            detail.leadingAnchor.constraint(equalTo: listPanel.trailingAnchor, constant: 20),
            detail.trailingAnchor.constraint(equalTo: trailingAnchor, constant: -28),
            detail.bottomAnchor.constraint(equalTo: listPanel.bottomAnchor),

            cover.topAnchor.constraint(equalTo: detail.topAnchor, constant: 18),
            cover.leadingAnchor.constraint(equalTo: detail.leadingAnchor, constant: 18),
            cover.trailingAnchor.constraint(equalTo: detail.trailingAnchor, constant: -18),
            cover.heightAnchor.constraint(equalTo: cover.widthAnchor, multiplier: 9.0 / 16.0),
            cover.bottomAnchor.constraint(lessThanOrEqualTo: info.topAnchor, constant: -18),
            info.leadingAnchor.constraint(equalTo: detail.leadingAnchor, constant: 22),
            info.trailingAnchor.constraint(equalTo: detail.trailingAnchor, constant: -22),
            info.bottomAnchor.constraint(equalTo: detail.bottomAnchor, constant: -22),

            busyStack.centerXAnchor.constraint(equalTo: busy.centerXAnchor),
            busyStack.centerYAnchor.constraint(equalTo: busy.centerYAnchor),
        ])
        for l in [titleLabel, artistLabel, versionLabel, statsLabel, bestLabel] {
            l.widthAnchor.constraint(lessThanOrEqualTo: info.widthAnchor).isActive = true
        }
    }

    override func layout() {
        super.layout()
        busy.frame = bounds
    }

    // MARK: данные

    func reload(select key: String? = nil) {
        let previous = key ?? selected?.key
        library.scan()
        applyFilter(select: previous)
    }

    private func applyFilter(select key: String? = nil) {
        let previous = key ?? selected?.key
        let q = search.stringValue.lowercased().trimmingCharacters(in: .whitespaces)
        filtered = q.isEmpty ? library.maps : library.maps.filter {
            "\($0.displayArtist) \($0.displayTitle) \($0.artist) \($0.title) \($0.version) \($0.creator)".lowercased().contains(q)
        }
        table.reloadData()
        empty.stringValue = library.maps.isEmpty
            ? "Тут пока пусто.\nПеретащи сюда трек (mp3, m4a, wav, flac…) — карта соберётся сама,\nили карту osu! (.osz / .osu)."
            : "Ничего не найдено"
        empty.isHidden = !filtered.isEmpty
        var row = 0
        if let k = previous, let i = filtered.firstIndex(where: { $0.key == k }) { row = i }
        if !filtered.isEmpty {
            table.selectRowIndexes(IndexSet(integer: row), byExtendingSelection: false)
            table.scrollRowToVisible(row)
        }
        showDetails()
    }

    var selected: Beatmap? {
        let r = table.selectedRow
        return r >= 0 && r < filtered.count ? filtered[r] : nil
    }

    func numberOfRows(in tableView: NSTableView) -> Int { filtered.count }

    func tableView(_ tableView: NSTableView, rowViewForRow row: Int) -> NSTableRowView? { SongRowView() }

    func tableView(_ tableView: NSTableView, viewFor tableColumn: NSTableColumn?, row: Int) -> NSView? {
        let id = NSUserInterfaceItemIdentifier("songRow")
        let cell = tableView.makeView(withIdentifier: id, owner: self) as? SongRow ?? {
            let c = SongRow(frame: .zero)
            c.identifier = id
            return c
        }()
        let m = filtered[row]
        cell.title.stringValue = m.displayTitle
        cell.sub.stringValue = "\(m.displayArtist) · \(m.version)"
        cell.stars.stringValue = String(format: "★ %.1f", m.stars)
        return cell
    }

    func tableViewSelectionDidChange(_ notification: Notification) { showDetails() }

    @objc private func doubleClicked() { if table.clickedRow >= 0 { playSelected() } }

    override func keyDown(with event: NSEvent) {
        if event.keyCode == 36 || event.keyCode == 76 { playSelected() } else { super.keyDown(with: event) }
    }

    private func showDetails() {
        guard let m = selected else {
            titleLabel.stringValue = library.maps.isEmpty ? "Добро пожаловать" : "Выбери песню"
            artistLabel.stringValue = ""
            versionLabel.stringValue = ""
            statsLabel.stringValue = ""
            bestLabel.stringValue = ""
            cover.image = nil
            playButton.isEnabled = false
            deleteButton.isEnabled = false
            stopPreview()
            return
        }
        titleLabel.stringValue = m.displayTitle
        artistLabel.stringValue = m.displayArtist + (m.creator.isEmpty ? "" : " · карта: \(m.creator)")
        versionLabel.stringValue = m.version + String(format: "  ★ %.1f", m.stars)
        let c = m.counts
        let len = Int(m.drainSeconds)
        let d = m.difficulty
        statsLabel.stringValue = String(format: "%d:%02d · %.0f BPM · %d кружков, %d слайдеров, %d спиннеров\nAR %.1f · OD %.1f · CS %.1f · HP %.1f",
                                        len / 60, len % 60, m.bpm, c.circles, c.sliders, c.spinners, d.ar, d.od, d.cs, d.hp)
        if let r = settings.best(m.key) {
            bestLabel.stringValue = String(format: "Рекорд: %@ · %d · %.2f%% · %d×", r.grade, r.score, r.accuracy * 100, r.combo)
        } else {
            bestLabel.stringValue = "Рекорда пока нет"
        }
        cover.image = m.backgroundURL.flatMap { NSImage(contentsOf: $0) } ?? NSApp.applicationIconImage
        playButton.isEnabled = true
        deleteButton.isEnabled = true
        startPreview(m)
    }

    // MARK: превью музыки

    private func startPreview(_ m: Beatmap) {
        guard let url = m.audioURL, url != previewURL else { return }
        stopPreview()
        guard let p = try? AVAudioPlayer(contentsOf: url) else { return }
        p.volume = settings.musicVolume * 0.6
        p.numberOfLoops = -1
        p.currentTime = m.previewTime > 0 ? m.previewTime / 1000 : p.duration * 0.4
        p.play()
        preview = p
        previewURL = url
    }

    func stopPreview() {
        preview?.stop()
        preview = nil
        previewURL = nil
    }

    func resumePreview() {
        if let m = selected { startPreview(m) }
    }

    // MARK: действия

    private func playSelected() {
        guard let m = selected else { return }
        stopPreview()
        delegate?.songSelect(play: m)
    }

    private func deleteSelected() {
        guard let m = selected, let win = window else { return }
        let alert = NSAlert()
        alert.messageText = "Удалить «\(m.displayTitle) [\(m.version)]»?"
        alert.informativeText = "Файл карты удалится из библиотеки. Когда у песни не останется сложностей, удалится и её папка."
        alert.addButton(withTitle: "Удалить")
        alert.addButton(withTitle: "Отмена")
        alert.beginSheetModal(for: win) { [weak self] r in
            guard r == .alertFirstButtonReturn, let self = self else { return }
            self.stopPreview()
            self.library.delete(m)
            self.reload()
        }
    }

    func pickFiles(audio: Bool) {
        guard let win = window else { return }
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = true
        panel.canChooseDirectories = false
        if audio {
            panel.allowedContentTypes = [.audio]
            panel.message = "Выбери треки — карта для каждого соберётся сама (3 сложности)"
        } else {
            panel.allowedContentTypes = ["osz", "osu"].compactMap { UTType(filenameExtension: $0) }
            panel.message = "Выбери карты osu! (.osz или .osu)"
        }
        panel.prompt = "Добавить"
        panel.beginSheetModal(for: win) { [weak self] r in
            if r == .OK { self?.importFiles(panel.urls) }
        }
    }

    func importFiles(_ urls: [URL]) {
        let items = urls.filter(Library.isImportable)
        let rejected = urls.filter { !Library.isImportable($0) }.map { $0.lastPathComponent }
        guard !items.isEmpty else {
            if !rejected.isEmpty { showError("Не тот формат", rejected.joined(separator: ", ") + "\n\nПодходят треки (mp3, m4a, wav, flac, aiff) и карты osu! (.osz, .osu). OGG macOS не проигрывает.") }
            return
        }
        stopPreview()
        busyLabel.stringValue = items.count == 1 ? "Импортирую «\(items[0].deletingPathExtension().lastPathComponent)»…" : "Импортирую \(items.count) файлов…"
        busy.isHidden = false
        let lib = library
        DispatchQueue.global(qos: .userInitiated).async {
            var errors: [String] = []
            var lastFolder: URL?
            for url in items {
                do { lastFolder = try lib.importAny(url) } catch { errors.append("\(url.lastPathComponent): \(error.localizedDescription)") }
            }
            DispatchQueue.main.async {
                self.busy.isHidden = true
                self.library.scan()
                let key = lastFolder.flatMap { folder in self.library.maps.first(where: { $0.folder?.standardizedFileURL == folder.standardizedFileURL })?.key }
                self.applyFilter(select: key)
                let problems = errors + rejected.map { "\($0): не тот формат" }
                if !problems.isEmpty { self.showError("Не всё получилось импортировать", problems.joined(separator: "\n")) }
            }
        }
    }

    private func showError(_ title: String, _ text: String) {
        let alert = NSAlert()
        alert.messageText = title
        alert.informativeText = text
        if let w = window { alert.beginSheetModal(for: w) } else { alert.runModal() }
    }

    // MARK: перетаскивание

    private func dropped(_ info: NSDraggingInfo) -> [URL] {
        info.draggingPasteboard.readObjects(forClasses: [NSURL.self], options: [.urlReadingFileURLsOnly: true]) as? [URL] ?? []
    }

    override func draggingEntered(_ sender: NSDraggingInfo) -> NSDragOperation { dropped(sender).isEmpty ? [] : .copy }

    override func performDragOperation(_ sender: NSDraggingInfo) -> Bool {
        let urls = dropped(sender)
        guard !urls.isEmpty else { return false }
        importFiles(urls)
        return true
    }

    // MARK: настройки

    private func showSettings() {
        guard let win = window else { return }
        let sheet = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 440, height: 410), styleMask: [.titled], backing: .buffered, defer: false)
        sheet.appearance = NSAppearance(named: .darkAqua)
        let root = FillView(color: Theme.panel)
        root.translatesAutoresizingMaskIntoConstraints = true
        sheet.contentView = root
        var local: [Action] = []
        func slider(_ title: String, _ value: Double, _ range: ClosedRange<Double>, _ format: @escaping (Double) -> String, _ set: @escaping (Double) -> Void) -> NSView {
            let label = Theme.label(title, font: .systemFont(ofSize: 13, weight: .medium))
            let valueLabel = Theme.label(format(value), font: Theme.rounded(12, .semibold), color: Theme.muted)
            let a = Action { s in
                let v = (s as? NSSlider)?.doubleValue ?? value
                valueLabel.stringValue = format(v)
                set(v)
            }
            local.append(a)
            let sl = NSSlider(value: value, minValue: range.lowerBound, maxValue: range.upperBound, target: a, action: #selector(Action.run(_:)))
            sl.isContinuous = true
            sl.translatesAutoresizingMaskIntoConstraints = false
            let top = NSStackView(views: [label, valueLabel])
            top.distribution = .equalSpacing
            let v = NSStackView(views: [top, sl])
            v.orientation = .vertical
            v.alignment = .leading
            v.spacing = 4
            top.widthAnchor.constraint(equalTo: v.widthAnchor).isActive = true
            sl.widthAnchor.constraint(equalTo: v.widthAnchor).isActive = true
            return v
        }
        let s = settings
        let rows: [NSView] = [
            Theme.label("Настройки", font: Theme.serif(22)),
            slider("Громкость музыки", Double(s.musicVolume), 0...1, { "\(Int($0 * 100))%" }) { s.musicVolume = Float($0) },
            slider("Громкость эффектов", Double(s.effectsVolume), 0...1, { "\(Int($0 * 100))%" }) { s.effectsVolume = Float($0) },
            slider("Смещение звука", s.offsetMs, -150...150, { "\(Int($0)) мс" }) { s.offsetMs = $0.rounded() },
            slider("Затемнение фона", s.dim, 0...1, { "\(Int($0 * 100))%" }) { s.dim = $0 },
            slider("Размер курсора", s.cursorSize, 0.6...1.8, { String(format: "%.1f×", $0) }) { s.cursorSize = $0 },
        ]
        let noFailAction = Action { b in s.noFail = (b as? NSButton)?.state == .on }
        local.append(noFailAction)
        let noFail = NSButton(checkboxWithTitle: "Без провала (здоровье не кончается)", target: noFailAction, action: #selector(Action.run(_:)))
        noFail.state = s.noFail ? .on : .off
        let mapColorsAction = Action { b in s.mapColors = (b as? NSButton)?.state == .on }
        local.append(mapColorsAction)
        let mapColors = NSButton(checkboxWithTitle: "Цвета кружков из карты osu! (смягчённые)", target: mapColorsAction, action: #selector(Action.run(_:)))
        mapColors.state = s.mapColors ? .on : .off
        let hint = Theme.label("Если удары кажутся «поздними», сдвинь смещение в плюс.", font: .systemFont(ofSize: 11.5), color: Theme.muted)
        let done = PillButton("Готово") { [weak win, weak sheet] in
            if let sh = sheet { win?.endSheet(sh) }
        }
        let stack = NSStackView(views: rows + [noFail, mapColors, hint, done])
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 12
        stack.translatesAutoresizingMaskIntoConstraints = false
        root.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.topAnchor.constraint(equalTo: root.topAnchor, constant: 22),
            stack.leadingAnchor.constraint(equalTo: root.leadingAnchor, constant: 24),
            stack.trailingAnchor.constraint(equalTo: root.trailingAnchor, constant: -24),
            stack.bottomAnchor.constraint(lessThanOrEqualTo: root.bottomAnchor, constant: -20),
        ])
        for r in rows.dropFirst() { r.widthAnchor.constraint(equalTo: stack.widthAnchor).isActive = true }
        actions.append(contentsOf: local)
        win.beginSheet(sheet) { [weak self] _ in
            self?.preview?.volume = s.musicVolume * 0.6
        }
    }
}

/// Итоги: оценка, счёт, точность, комбо, попадания.
final class ResultsView: NSView {
    init(session: GameSession, isRecord: Bool, onRetry: @escaping () -> Void, onBack: @escaping () -> Void) {
        super.init(frame: NSRect(x: 0, y: 0, width: 1280, height: 800))
        wantsLayer = true
        let m = session.map
        let grade = Theme.label(session.grade, font: Theme.serif(150, .bold), color: Theme.gradeColor(session.grade))
        let title = Theme.label(m.displayTitle, font: Theme.serif(30))
        let sub = Theme.label("\(m.displayArtist) · \(m.version)", font: .systemFont(ofSize: 15), color: Theme.muted)
        let score = Theme.label(String(format: "%08d", session.score), font: Theme.rounded(54, .heavy))
        let record = Theme.label(isRecord ? "Новый рекорд!" : "", font: .systemFont(ofSize: 15, weight: .semibold), color: Theme.accent)
        func stat(_ name: String, _ value: String, _ color: NSColor = Theme.text) -> NSView {
            let v = NSStackView(views: [Theme.label(value, font: Theme.rounded(26, .bold), color: color), Theme.label(name, font: .systemFont(ofSize: 12), color: Theme.muted)])
            v.orientation = .vertical
            v.spacing = 2
            return v
        }
        let c = session.counts
        let row1 = NSStackView(views: [
            stat("точность", String(format: "%.2f%%", session.accuracy * 100)),
            stat("макс. комбо", "\(session.maxCombo)×"),
        ])
        row1.spacing = 46
        let row2 = NSStackView(views: [
            stat("300", "\(c[.h300] ?? 0)", Theme.hex(0x8EC9FF)),
            stat("100", "\(c[.h100] ?? 0)", Theme.hex(0x7FD99A)),
            stat("50", "\(c[.h50] ?? 0)", Theme.hex(0xFFC46B)),
            stat("промахи", "\(c[.miss] ?? 0)", Theme.hex(0xE0605A)),
        ])
        row2.spacing = 40
        let retry = PillButton("Заново", onRetry)
        let back = PillButton("К списку песен", accent: false, onBack)
        let buttons = NSStackView(views: [retry, back])
        buttons.spacing = 12
        let info = NSStackView(views: [title, sub, score, record, row1, row2, buttons])
        info.orientation = .vertical
        info.alignment = .leading
        info.spacing = 10
        info.setCustomSpacing(22, after: record)
        info.setCustomSpacing(18, after: row1)
        info.setCustomSpacing(32, after: row2)
        let all = NSStackView(views: [grade, info])
        all.spacing = 56
        all.alignment = .centerY
        all.translatesAutoresizingMaskIntoConstraints = false
        addSubview(all)
        NSLayoutConstraint.activate([all.centerXAnchor.constraint(equalTo: centerXAnchor), all.centerYAnchor.constraint(equalTo: centerYAnchor)])
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) не используется") }

    override var wantsUpdateLayer: Bool { true }
    override func updateLayer() { layer?.backgroundColor = Theme.background.cgColor }
}
