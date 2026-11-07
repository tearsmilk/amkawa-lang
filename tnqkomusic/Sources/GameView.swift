import AppKit
import CoreVideo

protocol GameViewDelegate: AnyObject {
    func gameFinished(_ view: GameView, session: GameSession)
    func gameRestart(_ view: GameView)
    func gameQuit(_ view: GameView)
}

/// Игровой экран: поле 512×384 osu!-пикселей вписано в окно, отрисовка Core Graphics по CVDisplayLink.
final class GameView: NSView {
    let map: Beatmap
    let session: GameSession
    let clock: MusicClock?
    let sounds: HitSounds?
    let settings: Settings
    weak var delegate: GameViewDelegate?

    /// Время для самопроверки, когда нет музыки.
    var manualTime: Double = 0

    private var link: CVDisplayLink?
    private var paused = false
    private var ended = false
    private var heldKeys = Set<UInt16>()
    private var mouseButtons = 0
    private var background: CGImage?
    private var trail: [CGPoint] = []
    private var overlay: NSView?
    private var cursorHidden = false
    private var drawStart = 0
    private var pathCache: [Int: (scale: CGFloat, path: CGPath)] = [:]
    private var lastBreakFlash: Double = -10_000
    private var resignObserver: NSObjectProtocol?

    init(map: Beatmap, clock: MusicClock?, sounds: HitSounds?, settings: Settings) {
        self.map = map
        self.clock = clock
        self.sounds = sounds
        self.settings = settings
        session = GameSession(map: map)
        session.noFail = settings.noFail
        super.init(frame: NSRect(x: 0, y: 0, width: 1280, height: 800))
        wantsLayer = true
        layerContentsRedrawPolicy = .onSetNeedsDisplay
        if let url = map.backgroundURL, let img = NSImage(contentsOf: url) {
            background = img.cgImage(forProposedRect: nil, context: nil, hints: nil)
        }
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
    override var isOpaque: Bool { true }

    var time: Double { clock?.timeMs ?? manualTime }

    // MARK: запуск / пауза

    func start() {
        window?.makeFirstResponder(self)
        window?.acceptsMouseMovedEvents = true
        let first = map.firstTime
        let lead = max(map.audioLeadIn, 0) / 1000
        let from = min(0, (first - 1800) / 1000) - lead
        clock?.start(from: from)
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
        CVDisplayLinkSetOutputHandler(dl) { [weak self] _, _, _, _, _ in
            DispatchQueue.main.async { self?.tick() }
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
        needsDisplay = true
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
        addSubview(o)
        overlay = o
    }

    // MARK: кадр

    private var cursorView: CGPoint {
        guard let w = window else { return CGPoint(x: bounds.midX, y: bounds.midY) }
        return convert(w.mouseLocationOutsideOfEventStream, from: nil)
    }

    private var held: Bool { !heldKeys.isEmpty || mouseButtons > 0 }

    func tick() {
        guard !paused, !ended else { return }
        let t = time
        let c = cursorView
        session.update(t: t, cursor: toOsu(c), held: held)
        trail.append(c)
        if trail.count > 10 { trail.removeFirst(trail.count - 10) }
        needsDisplay = true
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
        session.press(at: time, pos: toOsu(cursorView))
    }

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

    override func keyUp(with event: NSEvent) { heldKeys.remove(event.keyCode) }

    override func mouseDown(with event: NSEvent) { mouseButtons += 1; press() }
    override func mouseUp(with event: NSEvent) { mouseButtons = max(0, mouseButtons - 1) }
    override func rightMouseDown(with event: NSEvent) { mouseButtons += 1; press() }
    override func rightMouseUp(with event: NSEvent) { mouseButtons = max(0, mouseButtons - 1) }

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

    // MARK: отрисовка

    override func draw(_ dirtyRect: NSRect) {
        guard let ctx = NSGraphicsContext.current?.cgContext else { return }
        let t = time
        drawBackground(ctx)

        let objects = map.objects
        let preempt = session.diff.preempt
        while drawStart < objects.count && objects[drawStart].endTime + 800 < t && session.states[drawStart].result != nil { drawStart += 1 }
        var visible: [Int] = []
        var i = drawStart
        while i < objects.count && objects[i].time - preempt <= t {
            if objects[i].endTime + 800 >= t || session.states[i].result == nil { visible.append(i) }
            i += 1
        }
        for idx in visible.reversed() { drawObject(ctx, idx, t: t) }
        for p in session.popups { drawPopup(ctx, p, t: t) }
        drawHUD(ctx, t: t)
        if !paused && !ended { drawCursor(ctx) }
    }

    private func drawBackground(_ ctx: CGContext) {
        ctx.setFillColor(Theme.background.cgColor)
        ctx.fill(bounds)
        if let bg = background {
            let iw = CGFloat(bg.width), ih = CGFloat(bg.height)
            let s = max(bounds.width / iw, bounds.height / ih)
            let r = CGRect(x: (bounds.width - iw * s) / 2, y: (bounds.height - ih * s) / 2, width: iw * s, height: ih * s)
            ctx.saveGState()
            // в перевёрнутой системе картинку нужно отразить обратно
            ctx.translateBy(x: 0, y: r.maxY + r.minY)
            ctx.scaleBy(x: 1, y: -1)
            ctx.draw(bg, in: r)
            ctx.restoreGState()
            ctx.setFillColor(CGColor(gray: 0, alpha: CGFloat(settings.dim)))
            ctx.fill(bounds)
        }
        // мягкая рамка поля
        let pf = CGRect(origin: toView(.zero), size: CGSize(width: 512 * scale, height: 384 * scale)).insetBy(dx: -40 * scale, dy: -40 * scale)
        ctx.setFillColor(CGColor(gray: 1, alpha: 0.02))
        ctx.addPath(CGPath(roundedRect: pf, cornerWidth: 24, cornerHeight: 24, transform: nil))
        ctx.fillPath()
    }

    private func color(_ o: HitObject) -> RGB {
        let colors = map.colors
        return colors[o.colorIndex % colors.count]
    }

    private func drawObject(_ ctx: CGContext, _ i: Int, t: Double) {
        let o = map.objects[i]
        let st = session.states[i]
        let d = session.diff
        let r = CGFloat(d.radius) * scale
        let appear = o.time - d.preempt
        var alpha = max(0, min(1, (t - appear) / d.fadeIn))
        let c = color(o)

        switch o.kind {
        case .circle:
            if let res = st.result {
                let age = t - st.resultTime
                if res == .miss {
                    alpha = max(0, 1 - age / 120) * 0.6
                    drawCircle(ctx, at: toView(o.pos), r: r, color: c, number: o.comboNumber, alpha: alpha, grow: 1)
                } else {
                    let k = max(0, min(1, age / 180))
                    drawCircle(ctx, at: toView(o.pos), r: r, color: c, number: nil, alpha: (1 - k) * 0.9, grow: 1 + 0.35 * CGFloat(k))
                }
                return
            }
            drawCircle(ctx, at: toView(o.pos), r: r, color: c, number: o.comboNumber, alpha: alpha, grow: 1)
            drawApproach(ctx, at: toView(o.pos), r: r, color: c, progress: (t - appear) / d.preempt, alpha: alpha)

        case .slider:
            if let _ = st.result {
                let age = t - st.resultTime
                alpha = max(0, 1 - age / 200)
                if alpha <= 0 { return }
            }
            drawSliderBody(ctx, i, o, r: r, color: c, alpha: alpha)
            // стрелка повтора
            if o.slides > 1 && st.result == nil {
                let span = Int(max(0, (t - o.time) / o.spanDuration))
                if span < o.slides - 1 {
                    let atEnd = span % 2 == 0
                    let tip = o.path?.point(at: atEnd ? 1 : 0) ?? o.pos
                    let back = o.path?.point(at: atEnd ? 0.97 : 0.03) ?? o.pos
                    drawArrow(ctx, at: toView(tip), towards: toView(back), r: r, alpha: alpha)
                }
            }
            // голова
            if st.headHit == nil {
                drawCircle(ctx, at: toView(o.pos), r: r, color: c, number: o.comboNumber, alpha: alpha, grow: 1)
                drawApproach(ctx, at: toView(o.pos), r: r, color: c, progress: (t - appear) / d.preempt, alpha: alpha)
            } else if st.headHit == true {
                let k = max(0, min(1, (t - st.headTime) / 180))
                if k < 1 { drawCircle(ctx, at: toView(o.pos), r: r, color: c, number: nil, alpha: (1 - k) * 0.9, grow: 1 + 0.35 * CGFloat(k)) }
            }
            // шар
            if t >= o.time && st.result == nil {
                let ball = toView(o.sliderPosition(at: min(t, o.endTime)))
                ctx.setFillColor(c.mixed(with: RGB(r: 1, g: 1, b: 1), 0.25).cg(alpha: 0.95))
                ctx.fillEllipse(in: CGRect(x: ball.x - r * 0.82, y: ball.y - r * 0.82, width: r * 1.64, height: r * 1.64))
                ctx.setStrokeColor(CGColor(gray: 1, alpha: 0.95))
                ctx.setLineWidth(max(2, r * 0.1))
                ctx.strokeEllipse(in: CGRect(x: ball.x - r * 0.82, y: ball.y - r * 0.82, width: r * 1.64, height: r * 1.64))
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

    private func drawCircle(_ ctx: CGContext, at p: CGPoint, r: CGFloat, color: RGB, number: Int?, alpha: Double, grow: CGFloat) {
        guard alpha > 0.001 else { return }
        let rr = r * grow
        let rect = CGRect(x: p.x - rr, y: p.y - rr, width: rr * 2, height: rr * 2)
        ctx.saveGState()
        ctx.setAlpha(CGFloat(alpha))
        ctx.beginTransparencyLayer(auxiliaryInfo: nil)
        // тень
        ctx.setFillColor(CGColor(gray: 0, alpha: 0.35))
        ctx.fillEllipse(in: rect.offsetBy(dx: 0, dy: rr * 0.06).insetBy(dx: -rr * 0.04, dy: -rr * 0.04))
        // градиентная заливка
        ctx.saveGState()
        ctx.addEllipse(in: rect)
        ctx.clip()
        let top = color.mixed(with: RGB(r: 1, g: 1, b: 1), 0.18).cg, bottom = color.mixed(with: RGB(r: 0, g: 0, b: 0), 0.22).cg
        if let g = CGGradient(colorsSpace: CGColorSpace(name: CGColorSpace.sRGB), colors: [top, bottom] as CFArray, locations: [0, 1]) {
            ctx.drawLinearGradient(g, start: CGPoint(x: p.x, y: rect.minY), end: CGPoint(x: p.x, y: rect.maxY), options: [])
        }
        ctx.restoreGState()
        ctx.setStrokeColor(CGColor(gray: 1, alpha: 1))
        ctx.setLineWidth(max(2, rr * 0.11))
        ctx.strokeEllipse(in: rect.insetBy(dx: rr * 0.055, dy: rr * 0.055))
        if let n = number {
            let font = Theme.rounded(r * 0.78, .heavy)
            let s = NSAttributedString(string: "\(n)", attributes: [.font: font, .foregroundColor: NSColor.white])
            let size = s.size()
            s.draw(at: CGPoint(x: p.x - size.width / 2, y: p.y - size.height / 2))
        }
        ctx.endTransparencyLayer()
        ctx.restoreGState()
    }

    private func drawApproach(_ ctx: CGContext, at p: CGPoint, r: CGFloat, color: RGB, progress: Double, alpha: Double) {
        let k = CGFloat(max(0, min(1, progress)))
        let ar = r * (1 + 3 * (1 - k))
        guard ar > r * 1.01 else { return }
        ctx.setStrokeColor(color.mixed(with: RGB(r: 1, g: 1, b: 1), 0.3).cg(alpha: alpha * 0.9))
        ctx.setLineWidth(max(2, r * 0.08))
        ctx.strokeEllipse(in: CGRect(x: p.x - ar, y: p.y - ar, width: ar * 2, height: ar * 2))
    }

    private func sliderPath(_ i: Int, _ o: HitObject) -> CGPath {
        let s = scale
        if let cached = pathCache[i], cached.scale == s { return cached.path }
        let path = CGMutablePath()
        let pts = o.path?.points ?? [o.pos]
        path.move(to: toView(pts[0]))
        for p in pts.dropFirst() { path.addLine(to: toView(p)) }
        if pts.count == 1 { path.addLine(to: toView(pts[0])) }
        pathCache[i] = (s, path)
        return path
    }

    private func drawSliderBody(_ ctx: CGContext, _ i: Int, _ o: HitObject, r: CGFloat, color: RGB, alpha: Double) {
        guard alpha > 0.001 else { return }
        let path = sliderPath(i, o)
        ctx.saveGState()
        ctx.setAlpha(CGFloat(alpha))
        ctx.beginTransparencyLayer(auxiliaryInfo: nil)
        ctx.setLineCap(.round)
        ctx.setLineJoin(.round)
        ctx.addPath(path)
        ctx.setStrokeColor(CGColor(gray: 1, alpha: 1))
        ctx.setLineWidth(r * 2)
        ctx.strokePath()
        ctx.addPath(path)
        ctx.setStrokeColor(color.mixed(with: RGB(r: 0.08, g: 0.06, b: 0.12), 0.6).cg)
        ctx.setLineWidth(r * 2 * 0.86)
        ctx.strokePath()
        ctx.addPath(path)
        ctx.setStrokeColor(color.mixed(with: RGB(r: 0.08, g: 0.06, b: 0.12), 0.35).cg(alpha: 0.6))
        ctx.setLineWidth(r * 2 * 0.45)
        ctx.strokePath()
        // круг на конце
        let end = toView(o.path?.point(at: 1) ?? o.pos)
        ctx.setStrokeColor(CGColor(gray: 1, alpha: 0.9))
        ctx.setLineWidth(max(2, r * 0.1))
        ctx.strokeEllipse(in: CGRect(x: end.x - r * 0.945, y: end.y - r * 0.945, width: r * 1.89, height: r * 1.89))
        ctx.endTransparencyLayer()
        ctx.restoreGState()
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
        let need = session.spinsRequired(o)
        let got = st.spin / (2 * .pi)
        let progress = CGFloat(max(0, min(1, got / need)))
        ctx.saveGState()
        ctx.setAlpha(CGFloat(alpha))
        ctx.setFillColor(CGColor(gray: 0, alpha: 0.35))
        ctx.fillEllipse(in: CGRect(x: c.x - big, y: c.y - big, width: big * 2, height: big * 2))
        ctx.setStrokeColor(CGColor(gray: 1, alpha: 0.25))
        ctx.setLineWidth(6)
        ctx.strokeEllipse(in: CGRect(x: c.x - big, y: c.y - big, width: big * 2, height: big * 2))
        ctx.setStrokeColor(Theme.accent.cgColor)
        ctx.setLineWidth(10)
        ctx.setLineCap(.round)
        ctx.addArc(center: c, radius: big, startAngle: -.pi / 2, endAngle: -.pi / 2 + 2 * .pi * progress, clockwise: false)
        ctx.strokePath()
        // круг, сжимающийся до конца спиннера
        let left = CGFloat(max(0, min(1, (o.endTime - t) / max(1, o.duration))))
        let ar = big * left
        if ar > 4 {
            ctx.setStrokeColor(Theme.pink.cgColor)
            ctx.setLineWidth(3)
            ctx.strokeEllipse(in: CGRect(x: c.x - ar, y: c.y - ar, width: ar * 2, height: ar * 2))
        }
        let text = t < o.time ? "Приготовься" : (progress >= 1 ? "Готово!" : "Крути!")
        let s = NSAttributedString(string: text, attributes: [.font: Theme.serif(30 * scale / 1.6), .foregroundColor: Theme.text])
        let size = s.size()
        s.draw(at: CGPoint(x: c.x - size.width / 2, y: c.y - size.height / 2))
        ctx.restoreGState()
    }

    private func drawPopup(_ ctx: CGContext, _ p: Popup, t: Double) {
        let age = (t - p.time) / 600
        guard age >= 0, age < 1 else { return }
        let color: NSColor
        switch p.judgement {
        case .h300: color = Theme.hex(0x8EC9FF)
        case .h100: color = Theme.hex(0x7FD99A)
        case .h50: color = Theme.hex(0xFFC46B)
        case .miss: color = Theme.hex(0xE0605A)
        }
        let size = (p.judgement == .miss ? 34 : 26) * scale / 1.6
        let s = NSAttributedString(string: p.judgement.text, attributes: [
            .font: Theme.rounded(size, .heavy),
            .foregroundColor: color.withAlphaComponent(CGFloat(1 - age) * (p.judgement == .h300 ? 0.55 : 1)),
        ])
        let v = toView(p.pos)
        let sz = s.size()
        s.draw(at: CGPoint(x: v.x - sz.width / 2, y: v.y - sz.height / 2 - CGFloat(age) * 24 * scale))
    }

    private func drawHUD(_ ctx: CGContext, t: Double) {
        let w = bounds.width, h = bounds.height
        // здоровье
        let barW = min(420, w * 0.36)
        ctx.setFillColor(CGColor(gray: 0, alpha: 0.45))
        ctx.addPath(CGPath(roundedRect: CGRect(x: 20, y: 18, width: barW, height: 10), cornerWidth: 5, cornerHeight: 5, transform: nil))
        ctx.fillPath()
        let hpColor = session.hp < 0.25 ? Theme.hex(0xE0605A) : Theme.accent
        ctx.setFillColor(hpColor.cgColor)
        ctx.addPath(CGPath(roundedRect: CGRect(x: 20, y: 18, width: max(10, barW * CGFloat(session.hp)), height: 10), cornerWidth: 5, cornerHeight: 5, transform: nil))
        ctx.fillPath()

        // счёт и точность
        let score = NSAttributedString(string: String(format: "%08d", session.score), attributes: [.font: Theme.rounded(34, .bold), .foregroundColor: Theme.text])
        let ss = score.size()
        score.draw(at: CGPoint(x: w - ss.width - 24, y: 12))
        let acc = NSAttributedString(string: String(format: "%.2f%%", session.accuracy * 100), attributes: [.font: Theme.rounded(20, .semibold), .foregroundColor: Theme.muted])
        let asz = acc.size()
        acc.draw(at: CGPoint(x: w - asz.width - 24, y: 12 + ss.height))

        // прогресс песни
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

        // комбо
        let flash = max(0, 1 - (t - lastBreakFlash) / 400)
        let comboColor = flash > 0 ? Theme.hex(0xE0605A) : Theme.text
        let combo = NSAttributedString(string: "\(session.combo)×", attributes: [.font: Theme.rounded(44, .heavy), .foregroundColor: comboColor])
        combo.draw(at: CGPoint(x: 22, y: h - combo.size().height - 14))

        if canSkip && !paused {
            let s = NSAttributedString(string: "Пробел — пропустить вступление", attributes: [.font: NSFont.systemFont(ofSize: 15, weight: .semibold), .foregroundColor: Theme.text])
            let sz = s.size()
            let r = CGRect(x: w - sz.width - 48, y: h - sz.height - 40, width: sz.width + 28, height: sz.height + 14)
            ctx.setFillColor(Theme.accent.withAlphaComponent(0.85).cgColor)
            ctx.addPath(CGPath(roundedRect: r, cornerWidth: r.height / 2, cornerHeight: r.height / 2, transform: nil))
            ctx.fillPath()
            s.draw(at: CGPoint(x: r.minX + 14, y: r.minY + 7))
        }
    }

    private func drawCursor(_ ctx: CGContext) {
        let k = CGFloat(settings.cursorSize)
        for (n, p) in trail.enumerated() {
            let a = CGFloat(n + 1) / CGFloat(trail.count + 1)
            let r = 7 * k * a
            ctx.setFillColor(Theme.pink.withAlphaComponent(0.35 * a).cgColor)
            ctx.fillEllipse(in: CGRect(x: p.x - r, y: p.y - r, width: r * 2, height: r * 2))
        }
        let c = cursorView
        let r = 13 * k
        ctx.setFillColor(Theme.text.withAlphaComponent(0.95).cgColor)
        ctx.fillEllipse(in: CGRect(x: c.x - r, y: c.y - r, width: r * 2, height: r * 2))
        ctx.setStrokeColor(Theme.accent.cgColor)
        ctx.setLineWidth(3 * k)
        ctx.strokeEllipse(in: CGRect(x: c.x - r, y: c.y - r, width: r * 2, height: r * 2))
        if held {
            ctx.setFillColor(Theme.accent.cgColor)
            ctx.fillEllipse(in: CGRect(x: c.x - r * 0.45, y: c.y - r * 0.45, width: r * 0.9, height: r * 0.9))
        }
    }
}
