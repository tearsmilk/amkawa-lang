import AppKit

// TnQkoTweaks — настройка внешнего вида и поведения macOS 11+ (Intel x64) без фоновой нагрузки.
if CommandLine.arguments.contains("--selftest") {
    exit(SelfTest.run())
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
