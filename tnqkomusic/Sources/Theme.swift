import AppKit

/// Тёмная игровая палитра: уголь, слоновая кость, терракотовый акцент.
enum Theme {
    static func hex(_ v: UInt32, _ alpha: CGFloat = 1) -> NSColor {
        NSColor(srgbRed: CGFloat((v >> 16) & 0xFF) / 255, green: CGFloat((v >> 8) & 0xFF) / 255, blue: CGFloat(v & 0xFF) / 255, alpha: alpha)
    }

    static let background = hex(0x17151F)
    static let panel = hex(0x221F2C)
    static let panelHover = hex(0x2C2838)
    static let selection = hex(0x3A2F3A)
    static let border = hex(0x363143)
    static let text = hex(0xF5F2EA)
    static let muted = hex(0xA39DAF)
    static let accent = hex(0xD97757)
    static let pink = hex(0xF28DB2)

    static func serif(_ size: CGFloat, _ weight: NSFont.Weight = .semibold) -> NSFont {
        let base = NSFont.systemFont(ofSize: size, weight: weight)
        if let d = base.fontDescriptor.withDesign(.serif), let f = NSFont(descriptor: d, size: size) { return f }
        return NSFont(name: "Georgia-Bold", size: size) ?? base
    }

    static func rounded(_ size: CGFloat, _ weight: NSFont.Weight = .bold) -> NSFont {
        let base = NSFont.monospacedDigitSystemFont(ofSize: size, weight: weight)
        if let d = base.fontDescriptor.withDesign(.rounded), let f = NSFont(descriptor: d, size: size) { return f }
        return base
    }

    static func label(_ text: String, font: NSFont = .systemFont(ofSize: 13), color: NSColor = Theme.text) -> NSTextField {
        let l = NSTextField(labelWithString: text)
        l.font = font
        l.textColor = color
        l.lineBreakMode = .byTruncatingTail
        l.translatesAutoresizingMaskIntoConstraints = false
        return l
    }

    static func gradeColor(_ g: String) -> NSColor {
        switch g {
        case "SS", "S": return hex(0xFFD36E)
        case "A": return hex(0x7FD99A)
        case "B": return hex(0x72B6F2)
        case "C": return pink
        default: return hex(0xE0605A)
        }
    }
}

final class Action: NSObject {
    private let fn: (Any?) -> Void
    init(_ fn: @escaping (Any?) -> Void) { self.fn = fn }
    @objc func run(_ sender: Any?) { fn(sender) }
}

final class FillView: NSView {
    var color: NSColor { didSet { needsDisplay = true } }
    var radius: CGFloat

    init(color: NSColor, radius: CGFloat = 0) {
        self.color = color
        self.radius = radius
        super.init(frame: .zero)
        wantsLayer = true
        translatesAutoresizingMaskIntoConstraints = false
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) не используется") }

    override var wantsUpdateLayer: Bool { true }

    override func updateLayer() {
        layer?.backgroundColor = color.cgColor
        layer?.cornerRadius = radius
    }
}

/// Кнопка-«пилюля» с акцентной заливкой.
final class PillButton: NSButton {
    private let fill: NSColor
    private let action_: Action

    init(_ title: String, accent: Bool = true, _ fn: @escaping () -> Void) {
        fill = accent ? Theme.accent : Theme.panelHover
        action_ = Action { _ in fn() }
        super.init(frame: .zero)
        self.title = title
        isBordered = false
        wantsLayer = true
        target = action_
        action = #selector(Action.run(_:))
        font = .systemFont(ofSize: 14, weight: .semibold)
        contentTintColor = Theme.text
        attributedTitle = NSAttributedString(string: title, attributes: [.foregroundColor: Theme.text, .font: NSFont.systemFont(ofSize: 14, weight: .semibold)])
        translatesAutoresizingMaskIntoConstraints = false
        heightAnchor.constraint(equalToConstant: 38).isActive = true
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) не используется") }

    override var intrinsicContentSize: NSSize {
        let s = super.intrinsicContentSize
        return NSSize(width: s.width + 36, height: 38)
    }

    override var wantsUpdateLayer: Bool { true }

    override func updateLayer() {
        layer?.cornerRadius = 19
        layer?.backgroundColor = (isEnabled ? fill : fill.withAlphaComponent(0.4)).cgColor
    }

    func setTitle(_ t: String) {
        title = t
        attributedTitle = NSAttributedString(string: t, attributes: [.foregroundColor: Theme.text, .font: NSFont.systemFont(ofSize: 14, weight: .semibold)])
    }
}
