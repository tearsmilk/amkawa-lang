import AppKit

/// Тёплая палитра: слоновая кость / уголь, терракотовый акцент.
enum Theme {
    static func hex(_ v: UInt32, _ alpha: CGFloat = 1) -> NSColor {
        NSColor(srgbRed: CGFloat((v >> 16) & 0xFF) / 255, green: CGFloat((v >> 8) & 0xFF) / 255,
                blue: CGFloat(v & 0xFF) / 255, alpha: alpha)
    }

    static func dynamic(_ light: UInt32, _ dark: UInt32) -> NSColor {
        NSColor(name: nil) { appearance in
            appearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua ? hex(dark) : hex(light)
        }
    }

    static let background = dynamic(0xFAF9F5, 0x1F1E1D)
    static let panel = dynamic(0xF0EEE6, 0x2B2A27)
    static let panelHover = dynamic(0xE8E5DA, 0x353430)
    static let border = dynamic(0xE0DCD0, 0x3E3D39)
    static let text = dynamic(0x262624, 0xF5F4EE)
    static let muted = dynamic(0x75736B, 0xA8A59B)
    static let accent = hex(0xD97757)

    static func serif(_ size: CGFloat, _ weight: NSFont.Weight = .semibold) -> NSFont {
        let base = NSFont.systemFont(ofSize: size, weight: weight)
        if let d = base.fontDescriptor.withDesign(.serif), let f = NSFont(descriptor: d, size: size) { return f }
        return NSFont(name: "Georgia-Bold", size: size) ?? base
    }

    static func label(_ text: String, font: NSFont = .systemFont(ofSize: 13), color: NSColor = Theme.text) -> NSTextField {
        let l = NSTextField(labelWithString: text)
        l.font = font
        l.textColor = color
        l.lineBreakMode = .byTruncatingTail
        l.translatesAutoresizingMaskIntoConstraints = false
        return l
    }

    static func caption(_ text: String) -> NSTextField {
        label(text.uppercased(), font: .systemFont(ofSize: 10.5, weight: .semibold), color: muted)
    }
}

/// Цель для target/action из замыкания (NSButton.target и NSMenuItem.target слабые — храните ссылку).
final class Action: NSObject {
    private let fn: (Any?) -> Void
    init(_ fn: @escaping (Any?) -> Void) { self.fn = fn }
    @objc func run(_ sender: Any?) { fn(sender) }
}

/// Вью с фоном и скруглением, цвет пересчитывается при смене светлой/тёмной темы.
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
