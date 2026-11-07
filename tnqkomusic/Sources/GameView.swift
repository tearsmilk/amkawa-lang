import AppKit
import CoreVideo

protocol GameViewDelegate: AnyObject {
    func gameFinished(_ view: GameView, session: GameSession)
    func gameRestart(_ view: GameView)
    func gameQuit(_ view: GameView)
}

/// Не даёт кадрам копиться в очереди главного потока: следующий тик ставится, только когда прошлый отработал.
private final class TickGate {
    private let lock = NSLock()
    private var pending = false

    func enter() -> Bool {
        lock.lock()
        defer { lock.unlock() }
        if pending { return false }
        pending = true
        return true
    }

    func leave() {
        lock.lock()
        pending = false
        lock.unlock()
    }
}

/// Прозрачный холст поверх фона; рисует через GameView.
private final class Canvas: NSView {
    weak var game: GameView?
    override var isFlipped: Bool { true }
    override var isOpaque: Bool { false }
    override func hitTest(_ point: NSPoint) -> NSView? { nil }
    override func draw(_ dirtyRect: NSRect) {
        guard let ctx = NSGraphicsContext.current?.cgContext else { return }
        game?.render(ctx)
    }
}

/// Фон: картинка — содержимое слоя (обычная, не перевёрнутая система координат).
private final class BackgroundView: NSView {
    var image: CGImage? { didSet { needsDisplay = true } }
    override func hitTest(_ point: NSPoint) -> NSView? { nil }
    override var wantsUpdateLayer: Bool { true }
    override func updateLayer() {
        layer?.backgroundColor = Theme.background.cgColor
        layer?.contents = image
        layer?.contentsGravity = .resizeAspectFill
        layer?.masksToBounds = true
    }
}

/// Курсор — отдельный слой: двигается по событию мыши сразу, не дожидаясь перерисовки кадра.
private final class CursorView: NSView {
    var pressed = false { didSet { if pressed != oldValue { needsDisplay = true } } }
    override func hitTest(_ point: NSPoint) -> NSView? { nil }
    override var isOpaque: Bool { false }
    override func draw(_ dirtyRect: NSRect) {
        let r = bounds.insetBy(dx: 3, dy: 3)
        Theme.text.withAlphaComponent(0.95).setFill()
        NSBezierPath(ovalIn: r).fill()
        Theme.accent.setStroke()
        let ring = NSBezierPath(ovalIn: r.insetBy(dx: 1.5, dy: 1.5))
        ring.lineWidth = 3
        ring.stroke()
        if pressed {
            Theme.accent.setFill()
            NSBezierPath(ovalIn: r.insetBy(dx: r.width * 0.28, dy: r.height * 0.28)).fill()
        }
    }
}

/// Игровой экран: поле 512×384 osu!-пикселей вписано в окно.
/// Фон — содержимое слоя (собирает видеокарта), кружки и слайдеры — заранее отрисованные спрайты.
final class GameView: NSView {
    let map: Beatmap
    let session: GameSession
    let clock: MusicClock?
    let sounds: HitSounds?
    let settings: Settings
    weak var delegate: GameViewDelegate?

    /// Время для самопроверки, когда нет музыки.
    var manualTime: Double = 0

    private let backdrop = BackgroundView()
    private let canvas = Canvas()
    private let cursor = CursorView()
    private var link: CVDisplayLink?
    private let gate = TickGate()
    private var paused = false
    private var ended = false
    private var heldKeys = Set<UInt16>()
    private var mouseButtons = 0
    private var background: CGImage?
    private var trail: [CGPoint] = []
    private var overlay: NSView?
    private var cursorHidden = false
    private var drawStart = 0
    private var lastBreakFlash: Double = -10_000
    private var resignObserver: NSObjectProtocol?

    // кэш спрайтов
    private var spriteKey: (radius: CGFloat, scale: CGFloat) = (0, 0)
    private var circleSprites: [String: CGImage] = [:]
    private var sliderSprites: [Int: (image: CGImage, rect: CGRect)] = [:]

    private static let hudScoreFont = Theme.rounded(34, .bold)
    private static let hudAccFont = Theme.rounded(20, .semibold)
    private static let hudComboFont = Theme.rounded(44, .heavy)
    private static let skipFont = NSFont.systemFont(ofSize: 15, weight: .semibold)
    private var popupFonts: [Int: NSFont] = [:]

    init(map: Beatmap, clock: MusicClock?, sounds: HitSounds?, settings: Settings) {
        self.map = map
        self.clock = clock
        self.sounds = sounds
        self.settings = settings
        session = GameSession(map: map)
        session.noFail = settings.noFail
        super.init(frame: NSRect(x: 0, y: 0, width: 1280, height: 800))
        wantsLayer = true
        if let url = map.backgroundURL, let img = NSImage(contentsOf: url) {
            background = GameView.dimmed(img, dim: settings.dim)
        }
        backdrop.wantsLayer = true
        backdrop.image = background
        backdrop.frame = bounds
        backdrop.autoresizingMask = [.width, .height]
        addSubview(backdrop)
        canvas.game = self
        canvas.wantsLayer = true
        canvas.layerContentsRedrawPolicy = .onSetNeedsDisplay
        canvas.frame = bounds
        canvas.autoresizingMask = [.width, .height]
        addSubview(canvas)
        let cs = 30 * CGFloat(settings.cursorSize)
        cursor.frame = NSRect(x: bounds.midX, y: bounds.midY, width: cs, height: cs)
        cursor.wantsLayer = true
        cursor.isHidden = true
        addSubview(cursor)
        session.onHit = { [weak self] _ in self?.sounds?.playHit() }
        session.onComboBreak = { [weak self] in
            guard let self = self else { return }
            self.sounds?.playComboBreak()
            self.lastBreakFlash = self.time
        }
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) не используется") }

    deinit { stopLink() }

    override var isFlipped: Bool { true }
    override var acceptsFirstResponder: Bool { true }
    var time: Double { clock?.timeMs ?? manualTime }

    /// Фон уменьшается до ~1920 px и затемняется один раз — дальше его только показывает слой.
    static func dimmed(_ img: NSImage, dim: Double) -> CGImage? {
        guard let src = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { return nil }
        let k = min(1, 1920 / CGFloat(max(src.width, 1)))
        let w = max(1, Int(CGFloat(src.width) * k)), h = max(1, Int(CGFloat(src.height) * k))
        guard let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: 0,
                                  space: CGColorSpace(name: CGColorSpace.sRGB)!, bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue) else { return src }
        ctx.interpolationQuality = .high
        ctx.draw(src, in: CGRect(x: 0, y: 0, width: w, height: h))
        ctx.setFillColor(CGColor(gray: 0, alpha: CGFloat(max(0, min(1, dim)))))
        ctx.fill(CGRect(x: 0, y: 0, width: w, height: h))
        return ctx.makeImage()
    }

    // MARK: запуск / пауза

    func start() {
        window?.makeFirstResponder(self)
        window?.acceptsMouseMovedEvents = true
        let first = map.firstTime
        let lead = max(map.audioLeadIn, 0) / 1000
        clock?.start(from: min(0, (first - 1800) / 1000) - lead)
        setCursorHidden(true)
        startLink()
        resignObserver = NotificationCenter.default.addObserver(forName: NSWindow.didResignKeyNotification, object: window, queue: .main) { [weak self] _ in
            guard let self = self, !self.paused, !self.ended else { return }
            self.pause()
        }
    }

    func teardown() {
        stopLink()
        clock?.stop()
        setCursorHidden(false)
        if let o = resignObserver { NotificationCenter.default.removeObserver(o) }
        resignObserver = nil
    }

    private func startLink() {
        guard link == nil else { return }
        var l: CVDisplayLink?
        CVDisplayLinkCreateWithActiveCGDisplays(&l)
        guard let dl = l else { return }
        let gate = self.gate
        CVDisplayLinkSetOutputHandler(dl) { [weak self] _, _, _, _, _ in
            guard gate.enter() else { return kCVReturnSuccess }
            DispatchQueue.main.async {
                self?.tick()
                gate.leave()
            }
            return kCVReturnSuccess
        }
        CVDisplayLinkStart(dl)
        link = dl
    }

    private func stopLink() {
        if let l = link { CVDisplayLinkStop(l) }
        link = nil
    }

    private func setCursorHidden(_ hidden: Bool) {
        cursor.isHidden = !hidden
        guard hidden != cursorHidden else { return }
        if hidden { NSCursor.hide() } else { NSCursor.unhide() }
        cursorHidden = hidden
    }

    func pause() {
        guard !paused, !ended else { return }
        paused = true
        clock?.pause()
        setCursorHidden(false)
        showOverlay(title: "Пауза", subtitle: "Esc — продолжить", resume: true)
        canvas.needsDisplay = true
    }

    func resume() {
        guard paused else { return }
        paused = false
        overlay?.removeFromSuperview()
        overlay = nil
        heldKeys.removeAll()
        mouseButtons = 0
        clock?.resume()
        setCursorHidden(true)
        window?.makeFirstResponder(self)
    }

    private func fail() {
        ended = true
        clock?.pause()
        setCursorHidden(false)
        showOverlay(title: "Провал", subtitle: "Здоровье закончилось. Можно включить «Без провала» в настройках.", resume: false)
    }

    private func showOverlay(title: String, subtitle: String, resume: Bool) {
        overlay?.removeFromSuperview()
        let o = FillView(color: NSColor.black.withAlphaComponent(0.62))
        o.translatesAutoresizingMaskIntoConstraints = true
        o.frame = bounds
        o.autoresizingMask = [.width, .height]
        let t = Theme.label(title, font: Theme.serif(44), color: title == "Провал" ? Theme.hex(0xE0605A) : Theme.text)
        let s = Theme.label(subtitle, font: .systemFont(ofSize: 14), color: Theme.muted)
        var buttons: [NSView] = []
        if resume { buttons.append(PillButton("Продолжить") { [weak self] in self?.resume() }) }
        buttons.append(PillButton("Заново", accent: !resume) { [weak self] in
            guard let self = self else { return }
            self.delegate?.gameRestart(self)
        })
        buttons.append(PillButton("К списку песен", accent: false) { [weak self] in
            guard let self = self else { return }
            self.delegate?.gameQuit(self)
        })
        let stack = NSStackView(views: [t, s] + buttons)
        stack.orientation = .vertical
        stack.spacing = 12
        stack.setCustomSpacing(26, after: s)
        stack.translatesAutoresizingMaskIntoConstraints = false
        for b in buttons { b.widthAnchor.constraint(equalToConstant: 240).isActive = true }
        o.addSubview(stack)
        NSLayoutConstraint.activate([stack.centerXAnchor.constraint(equalTo: o.centerXAnchor), stack.centerYAnchor.constraint(equalTo: o.centerYAnchor)])
        addSubview(o, positioned: .above, relativeTo: cursor)
        overlay = o
    }

    // MARK: кадр

    private var cursorPoint: CGPoint {
        guard let w = window else { return CGPoint(x: bounds.midX, y: bounds.midY) }
        return convert(w.mouseLocationOutsideOfEventStream, from: nil)
    }

    private var held: Bool { !heldKeys.isEmpty || mouseButtons > 0 }

    private func moveCursor(_ p: CGPoint) {
        let s = cursor.frame.width
        cursor.setFrameOrigin(NSPoint(x: p.x - s / 2, y: p.y - s / 2))
        cursor.pressed = held
    }

    func tick() {
        guard !paused, !ended else { return }
        let t = time
        let c = cursorPoint
        moveCursor(c)
        session.update(t: t, cursor: toOsu(c), held: held)
        trail.append(c)
        if trail.count > 8 { trail.removeFirst(trail.count - 8) }
        canvas.needsDisplay = true
        if session.failed {
            fail()
        } else if session.finished && t > session.endTime + 1200 {
            ended = true
            teardown()
            delegate?.gameFinished(self, session: session)
        }
    }

    // MARK: ввод

    private func press() {
        guard !paused, !ended else { return }
        session.press(at: time, pos: toOsu(cursorPoint))
        cursor.pressed = true
    }

    override func mouseMoved(with event: NSEvent) { if !paused { moveCursor(convert(event.locationInWindow, from: nil)) } }
    override func mouseDragged(with event: NSEvent) { mouseMoved(with: event) }
    override func rightMouseDragged(with event: NSEvent) { mouseMoved(with: event) }

    override func keyDown(with event: NSEvent) {
        switch event.keyCode {
        case 53:  // Esc
            if paused { resume() } else { pause() }
        case 49:  // пробел — пропустить вступление
            skipIntro()
        case 6, 7:  // Z, X
            if event.isARepeat { return }
            heldKeys.insert(event.keyCode)
            press()
        default:
            break
        }
    }

    override func keyUp(with event: NSEvent) {
        heldKeys.remove(event.keyCode)
        cursor.pressed = held
    }

    override func mouseDown(with event: NSEvent) { mouseButtons += 1; press() }
    override func mouseUp(with event: NSEvent) { mouseButtons = max(0, mouseButtons - 1); cursor.pressed = held }
    override func rightMouseDown(with event: NSEvent) { mouseButtons += 1; press() }
    override func rightMouseUp(with event: NSEvent) { mouseButtons = max(0, mouseButtons - 1); cursor.pressed = held }

    var canSkip: Bool { map.firstTime - time > 3000 }

    func skipIntro() {
        guard canSkip, !paused, !ended, let clock = clock else { return }
        clock.start(from: (map.firstTime - 2000) / 1000 + settings.offsetMs / 1000)
    }

    // MARK: координаты

    private var scale: CGFloat { min(bounds.width / 640, bounds.height / 480) }

    private var origin: CGPoint {
        let s = scale
        return CGPoint(x: (bounds.width - 512 * s) / 2, y: (bounds.height - 384 * s) / 2 + 8 * s)
    }

    func toView(_ p: CGPoint) -> CGPoint {
        let s = scale, o = origin
        return CGPoint(x: o.x + p.x * s, y: o.y + p.y * s)
    }

    func toOsu(_ p: CGPoint) -> CGPoint {
        let s = scale, o = origin
        return CGPoint(x: (p.x - o.x) / s, y: (p.y - o.y) / s)
    }

    // MARK: спрайты

    private var backingScale: CGFloat { window?.backingScaleFactor ?? 2 }

    /// Картинка size×size точек с началом координат в левом верхнем углу (как у холста).
    private func sprite(width: CGFloat, height: CGFloat, _ draw: (CGContext) -> Void) -> CGImage? {
        let s = backingScale
        let w = max(1, Int(ceil(width * s))), h = max(1, Int(ceil(height * s)))
        guard let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: 0,
                                  space: CGColorSpace(name: CGColorSpace.sRGB)!, bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { return nil }
        ctx.scaleBy(x: s, y: s)
        ctx.translateBy(x: 0, y: height)
        ctx.scaleBy(x: 1, y: -1)
        let previous = NSGraphicsContext.current
        NSGraphicsContext.current = NSGraphicsContext(cgContext: ctx, flipped: true)
        draw(ctx)
        NSGraphicsContext.current = previous
        return ctx.makeImage()
    }

    /// Рисует спрайт в перевёрнутом холсте без отражения.
    private func blit(_ ctx: CGContext, _ img: CGImage, in r: CGRect, alpha: CGFloat) {
        guard alpha > 0.003 else { return }
        ctx.saveGState()
        ctx.setAlpha(alpha)
        ctx.translateBy(x: 0, y: r.minY + r.maxY)
        ctx.scaleBy(x: 1, y: -1)
        ctx.draw(img, in: r)
        ctx.restoreGState()
    }

    private func validateSprites(radius r: CGFloat) {
        let s = backingScale
        if spriteKey.radius != r || spriteKey.scale != s {
            spriteKey = (r, s)
            circleSprites.removeAll()
            sliderSprites.removeAll()
        }
    }

    private func circleSprite(colorIndex: Int, color: RGB, number: Int?, r: CGFloat) -> CGImage? {
        let key = "\(colorIndex)-\(number ?? 0)"
        if let img = circleSprites[key] { return img }
        let size = r * 2.3
        let img = sprite(width: size, height: size) { ctx in
            let c = CGPoint(x: size / 2, y: size / 2)
            let rect = CGRect(x: c.x - r, y: c.y - r, width: r * 2, height: r * 2)
            ctx.setFillColor(CGColor(gray: 0, alpha: 0.35))
            ctx.fillEllipse(in: rect.offsetBy(dx: 0, dy: r * 0.06).insetBy(dx: -r * 0.04, dy: -r * 0.04))
            ctx.saveGState()
            ctx.addEllipse(in: rect)
            ctx.clip()
            let top = color.mixed(with: RGB(r: 1, g: 1, b: 1), 0.28).cg, bottom = color.mixed(with: RGB(r: 0.1, g: 0.2, b: 0.18), 0.12).cg
            if let g = CGGradient(colorsSpace: CGColorSpace(name: CGColorSpace.sRGB), colors: [top, bottom] as CFArray, locations: [0, 1]) {
                ctx.drawLinearGradient(g, start: CGPoint(x: c.x, y: rect.minY), end: CGPoint(x: c.x, y: rect.maxY), options: [])
            }
            ctx.restoreGState()
            ctx.setStrokeColor(CGColor(gray: 1, alpha: 1))
            ctx.setLineWidth(max(2, r * 0.11))
            ctx.strokeEllipse(in: rect.insetBy(dx: r * 0.055, dy: r * 0.055))
            if let n = number {
                let s = NSAttributedString(string: "\(n)", attributes: [.font: Theme.rounded(r * 0.78, .heavy), .foregroundColor: Theme.accentText])
                let sz = s.size()
                s.draw(at: CGPoint(x: c.x - sz.width / 2, y: c.y - sz.height / 2))
            }
        }
        circleSprites[key] = img
        return img
    }

    private func drawCircle(_ ctx: CGContext, _ o: HitObject, at p: CGPoint, r: CGFloat, number: Int?, alpha: Double, grow: CGFloat) {
        guard alpha > 0.003, let img = circleSprite(colorIndex: o.colorIndex, color: color(o), number: number, r: r) else { return }
        let size = r * 2.3 * grow
        blit(ctx, img, in: CGRect(x: p.x - size / 2, y: p.y - size / 2, width: size, height: size), alpha: CGFloat(alpha))
    }

    /// Тело слайдера рисуется один раз в картинку по своим границам.
    private func sliderSprite(_ i: Int, _ o: HitObject, r: CGFloat, color: RGB) -> (image: CGImage, rect: CGRect)? {
        if let s = sliderSprites[i] { return s }
        let pts = (o.path?.points ?? [o.pos]).map(toView)
        var minX = CGFloat.infinity, minY = CGFloat.infinity, maxX = -CGFloat.infinity, maxY = -CGFloat.infinity
        for p in pts { minX = min(minX, p.x); minY = min(minY, p.y); maxX = max(maxX, p.x); maxY = max(maxY, p.y) }
        let rect = CGRect(x: minX - r - 4, y: minY - r - 4, width: maxX - minX + 2 * r + 8, height: maxY - minY + 2 * r + 8)
        guard let img = sprite(width: rect.width, height: rect.height, { ctx in
            let path = CGMutablePath()
            path.move(to: CGPoint(x: pts[0].x - rect.minX, y: pts[0].y - rect.minY))
            for p in pts.dropFirst() { path.addLine(to: CGPoint(x: p.x - rect.minX, y: p.y - rect.minY)) }
            if pts.count == 1 { path.addLine(to: CGPoint(x: pts[0].x - rect.minX + 0.1, y: pts[0].y - rect.minY)) }
            ctx.setLineCap(.round)
            ctx.setLineJoin(.round)
            let dark = RGB(r: 0.08, g: 0.06, b: 0.12)
            ctx.addPath(path); ctx.setStrokeColor(CGColor(gray: 1, alpha: 1)); ctx.setLineWidth(r * 2); ctx.strokePath()
            ctx.addPath(path); ctx.setStrokeColor(color.mixed(with: dark, 0.55).cg); ctx.setLineWidth(r * 1.72); ctx.strokePath()
            ctx.addPath(path); ctx.setStrokeColor(color.mixed(with: dark, 0.3).cg); ctx.setLineWidth(r * 0.9); ctx.strokePath()
            let end = CGPoint(x: (pts.last?.x ?? 0) - rect.minX, y: (pts.last?.y ?? 0) - rect.minY)
            ctx.setStrokeColor(CGColor(gray: 1, alpha: 0.9))
            ctx.setLineWidth(max(2, r * 0.1))
            ctx.strokeEllipse(in: CGRect(x: end.x - r * 0.945, y: end.y - r * 0.945, width: r * 1.89, height: r * 1.89))
        }) else { return nil }
        sliderSprites[i] = (img, rect)
        return (img, rect)
    }

    // MARK: отрисовка

    func render(_ ctx: CGContext) {
        let t = time
        let r = CGFloat(session.diff.radius) * scale
        validateSprites(radius: r)
        ctx.interpolationQuality = .medium

        let objects = map.objects
        let preempt = session.diff.preempt
        while drawStart < objects.count && objects[drawStart].endTime + 800 < t && session.states[drawStart].result != nil {
            sliderSprites[drawStart] = nil
            drawStart += 1
        }
        var visible: [Int] = []
        var i = drawStart
        while i < objects.count && objects[i].time - preempt <= t {
            if objects[i].endTime + 800 >= t || session.states[i].result == nil { visible.append(i) }
            i += 1
        }
        for idx in visible.reversed() { drawObject(ctx, idx, t: t, r: r) }
        for p in session.popups { drawPopup(ctx, p, t: t) }
        drawHUD(ctx, t: t)
        if !paused && !ended { drawTrail(ctx) }
    }

    private func color(_ o: HitObject) -> RGB {
        let colors = map.colors
        return colors[o.colorIndex % colors.count]
    }

    private func drawObject(_ ctx: CGContext, _ i: Int, t: Double, r: CGFloat) {
        let o = map.objects[i]
        let st = session.states[i]
        let d = session.diff
        let appear = o.time - d.preempt
        var alpha = max(0, min(1, (t - appear) / d.fadeIn))
        let c = color(o)

        switch o.kind {
        case .circle:
            if let res = st.result {
                let age = t - st.resultTime
                if res == .miss {
                    drawCircle(ctx, o, at: toView(o.pos), r: r, number: o.comboNumber, alpha: max(0, 1 - age / 120) * 0.6, grow: 1)
                } else {
                    let k = max(0, min(1, age / 180))
                    drawCircle(ctx, o, at: toView(o.pos), r: r, number: nil, alpha: (1 - k) * 0.9, grow: 1 + 0.35 * CGFloat(k))
                }
                return
            }
            drawCircle(ctx, o, at: toView(o.pos), r: r, number: o.comboNumber, alpha: alpha, grow: 1)
            drawApproach(ctx, at: toView(o.pos), r: r, color: c, progress: (t - appear) / d.preempt, alpha: alpha)

        case .slider:
            if st.result != nil {
                alpha = max(0, 1 - (t - st.resultTime) / 200)
                if alpha <= 0 { return }
            }
            if let body = sliderSprite(i, o, r: r, color: c) {
                blit(ctx, body.image, in: body.rect, alpha: CGFloat(alpha * 0.92))
            }
            if o.slides > 1 && st.result == nil {
                let span = Int(max(0, (t - o.time) / o.spanDuration))
                if span < o.slides - 1 {
                    let atEnd = span % 2 == 0
                    let tip = o.path?.point(at: atEnd ? 1 : 0) ?? o.pos
                    let back = o.path?.point(at: atEnd ? 0.97 : 0.03) ?? o.pos
                    drawArrow(ctx, at: toView(tip), towards: toView(back), r: r, alpha: alpha)
                }
            }
            if st.headHit == nil {
                drawCircle(ctx, o, at: toView(o.pos), r: r, number: o.comboNumber, alpha: alpha, grow: 1)
                drawApproach(ctx, at: toView(o.pos), r: r, color: c, progress: (t - appear) / d.preempt, alpha: alpha)
            } else if st.headHit == true {
                let k = max(0, min(1, (t - st.headTime) / 180))
                if k < 1 { drawCircle(ctx, o, at: toView(o.pos), r: r, number: nil, alpha: (1 - k) * 0.9, grow: 1 + 0.35 * CGFloat(k)) }
            }
            if t >= o.time && st.result == nil {
                let ball = toView(o.sliderPosition(at: min(t, o.endTime)))
                let br = r * 0.82
                let rect = CGRect(x: ball.x - br, y: ball.y - br, width: br * 2, height: br * 2)
                ctx.setFillColor(c.mixed(with: RGB(r: 1, g: 1, b: 1), 0.25).cg(alpha: 0.95))
                ctx.fillEllipse(in: rect)
                ctx.setStrokeColor(CGColor(gray: 1, alpha: 0.95))
                ctx.setLineWidth(max(2, r * 0.1))
                ctx.strokeEllipse(in: rect)
                if st.tracking {
                    let fr = r * 2.0
                    ctx.setStrokeColor(c.cg(alpha: 0.7))
                    ctx.setLineWidth(max(2, r * 0.08))
                    ctx.strokeEllipse(in: CGRect(x: ball.x - fr, y: ball.y - fr, width: fr * 2, height: fr * 2))
                }
            }

        case .spinner:
            if st.result != nil && t - st.resultTime > 250 { return }
            drawSpinner(ctx, i, o, t: t, alpha: st.result == nil ? alpha : max(0, 1 - (t - st.resultTime) / 250))
        }
    }

    private func drawApproach(_ ctx: CGContext, at p: CGPoint, r: CGFloat, color: RGB, progress: Double, alpha: Double) {
        let k = CGFloat(max(0, min(1, progress)))
        let ar = r * (1 + 3 * (1 - k))
        guard ar > r * 1.01, alpha > 0.003 else { return }
        ctx.setStrokeColor(color.mixed(with: RGB(r: 1, g: 1, b: 1), 0.3).cg(alpha: alpha * 0.9))
        ctx.setLineWidth(max(2, r * 0.08))
        ctx.strokeEllipse(in: CGRect(x: p.x - ar, y: p.y - ar, width: ar * 2, height: ar * 2))
    }

    private func drawArrow(_ ctx: CGContext, at p: CGPoint, towards q: CGPoint, r: CGFloat, alpha: Double) {
        let a = atan2(q.y - p.y, q.x - p.x)
        let s = r * 0.45
        let path = CGMutablePath()
        path.move(to: CGPoint(x: p.x + cos(a) * s, y: p.y + sin(a) * s))
        path.addLine(to: CGPoint(x: p.x + cos(a + 2.4) * s, y: p.y + sin(a + 2.4) * s))
        path.addLine(to: CGPoint(x: p.x + cos(a - 2.4) * s, y: p.y + sin(a - 2.4) * s))
        path.closeSubpath()
        ctx.setFillColor(CGColor(gray: 1, alpha: CGFloat(alpha)))
        ctx.addPath(path)
        ctx.fillPath()
    }

    private func drawSpinner(_ ctx: CGContext, _ i: Int, _ o: HitObject, t: Double, alpha: Double) {
        let c = toView(GameSession.spinCenter)
        let big = 170 * scale
        let st = session.states[i]
        let progress = CGFloat(max(0, min(1, st.spin / (2 * .pi) / session.spinsRequired(o))))
        let a = CGFloat(alpha)
        let circle = CGRect(x: c.x - big, y: c.y - big, width: big * 2, height: big * 2)
        ctx.setFillColor(CGColor(gray: 0, alpha: 0.35 * a))
        ctx.fillEllipse(in: circle)
        ctx.setStrokeColor(CGColor(gray: 1, alpha: 0.25 * a))
        ctx.setLineWidth(6)
        ctx.strokeEllipse(in: circle)
        if progress > 0 {
            ctx.setStrokeColor(Theme.accent.withAlphaComponent(a).cgColor)
            ctx.setLineWidth(10)
            ctx.setLineCap(.round)
            ctx.addArc(center: c, radius: big, startAngle: -.pi / 2, endAngle: -.pi / 2 + 2 * .pi * progress, clockwise: false)
            ctx.strokePath()
        }
        let ar = big * CGFloat(max(0, min(1, (o.endTime - t) / max(1, o.duration))))
        if ar > 4 {
            ctx.setStrokeColor(Theme.pink.withAlphaComponent(a).cgColor)
            ctx.setLineWidth(3)
            ctx.strokeEllipse(in: CGRect(x: c.x - ar, y: c.y - ar, width: ar * 2, height: ar * 2))
        }
        let text = t < o.time ? "Приготовься" : (progress >= 1 ? "Готово!" : "Крути!")
        let s = NSAttributedString(string: text, attributes: [.font: popupFont(Int(30 * scale / 1.6)), .foregroundColor: Theme.text.withAlphaComponent(a)])
        let size = s.size()
        s.draw(at: CGPoint(x: c.x - size.width / 2, y: c.y - size.height / 2))
    }

    private func popupFont(_ size: Int) -> NSFont {
        if let f = popupFonts[size] { return f }
        let f = Theme.rounded(CGFloat(max(8, size)), .heavy)
        popupFonts[size] = f
        return f
    }

    private func drawPopup(_ ctx: CGContext, _ p: Popup, t: Double) {
        let age = (t - p.time) / 600
        guard age >= 0, age < 1 else { return }
        if p.judgement == .h300 { return }  // 300 — норма, не мельтешим
        let color: NSColor
        switch p.judgement {
        case .h300: color = Theme.hex(0x8EC9FF)
        case .h100: color = Theme.hex(0x7FD99A)
        case .h50: color = Theme.hex(0xFFC46B)
        case .miss: color = Theme.hex(0xE0605A)
        }
        let size = Int((p.judgement == .miss ? 34 : 26) * scale / 1.6)
        let s = NSAttributedString(string: p.judgement.text, attributes: [.font: popupFont(size), .foregroundColor: color.withAlphaComponent(CGFloat(1 - age))])
        let v = toView(p.pos)
        let sz = s.size()
        s.draw(at: CGPoint(x: v.x - sz.width / 2, y: v.y - sz.height / 2 - CGFloat(age) * 24 * scale))
    }

    private func drawHUD(_ ctx: CGContext, t: Double) {
        let w = bounds.width, h = bounds.height
        let barW = min(420, w * 0.36)
        ctx.setFillColor(CGColor(gray: 0, alpha: 0.45))
        ctx.addPath(CGPath(roundedRect: CGRect(x: 20, y: 18, width: barW, height: 10), cornerWidth: 5, cornerHeight: 5, transform: nil))
        ctx.fillPath()
        ctx.setFillColor((session.hp < 0.25 ? Theme.hex(0xE0605A) : Theme.accent).cgColor)
        ctx.addPath(CGPath(roundedRect: CGRect(x: 20, y: 18, width: max(10, barW * CGFloat(session.hp)), height: 10), cornerWidth: 5, cornerHeight: 5, transform: nil))
        ctx.fillPath()

        let score = NSAttributedString(string: String(format: "%08d", session.score), attributes: [.font: Self.hudScoreFont, .foregroundColor: Theme.text])
        let ss = score.size()
        score.draw(at: CGPoint(x: w - ss.width - 24, y: 12))
        let acc = NSAttributedString(string: String(format: "%.2f%%", session.accuracy * 100), attributes: [.font: Self.hudAccFont, .foregroundColor: Theme.muted])
        let asz = acc.size()
        acc.draw(at: CGPoint(x: w - asz.width - 24, y: 12 + ss.height))

        let start = map.firstTime, end = max(start + 1, map.endTime)
        let prog = CGFloat(max(0, min(1, (t - start) / (end - start))))
        let pc = CGPoint(x: w - asz.width - 46, y: 12 + ss.height + asz.height / 2)
        ctx.setStrokeColor(CGColor(gray: 1, alpha: 0.2))
        ctx.setLineWidth(3)
        ctx.strokeEllipse(in: CGRect(x: pc.x - 9, y: pc.y - 9, width: 18, height: 18))
        if prog > 0 {
            ctx.setStrokeColor(Theme.pink.cgColor)
            ctx.addArc(center: pc, radius: 9, startAngle: -.pi / 2, endAngle: -.pi / 2 + 2 * .pi * prog, clockwise: false)
            ctx.strokePath()
        }

        let flash = t - lastBreakFlash < 400
        let combo = NSAttributedString(string: "\(session.combo)×", attributes: [.font: Self.hudComboFont, .foregroundColor: flash ? Theme.hex(0xE0605A) : Theme.text])
        combo.draw(at: CGPoint(x: 22, y: h - combo.size().height - 14))

        if canSkip && !paused {
            let s = NSAttributedString(string: "Пробел — пропустить вступление", attributes: [.font: Self.skipFont, .foregroundColor: Theme.accentText])
            let sz = s.size()
            let r = CGRect(x: w - sz.width - 48, y: h - sz.height - 40, width: sz.width + 28, height: sz.height + 14)
            ctx.setFillColor(Theme.accent.withAlphaComponent(0.85).cgColor)
            ctx.addPath(CGPath(roundedRect: r, cornerWidth: r.height / 2, cornerHeight: r.height / 2, transform: nil))
            ctx.fillPath()
            s.draw(at: CGPoint(x: r.minX + 14, y: r.minY + 7))
        }
    }

    private func drawTrail(_ ctx: CGContext) {
        let k = CGFloat(settings.cursorSize)
        for (n, p) in trail.dropLast().enumerated() {
            let a = CGFloat(n + 1) / CGFloat(trail.count + 1)
            let r = 6 * k * a
            ctx.setFillColor(Theme.pink.withAlphaComponent(0.3 * a).cgColor)
            ctx.fillEllipse(in: CGRect(x: p.x - r, y: p.y - r, width: r * 2, height: r * 2))
        }
    }
}
