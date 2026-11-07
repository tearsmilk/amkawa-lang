import AppKit

// TnQkoWallpaper — живые обои из видео для macOS 11+ (Intel x64).
if CommandLine.arguments.contains("--selftest") {
    exit(SelfTest.run())
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.accessory)
app.run()
