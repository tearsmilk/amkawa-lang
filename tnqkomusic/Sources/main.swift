import AppKit

// TnQkoMusically — ритм-игра «кликай по кружкам» для macOS 11+ (Intel x64).
if CommandLine.arguments.contains("--selftest") {
    exit(SelfTest.run())
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
