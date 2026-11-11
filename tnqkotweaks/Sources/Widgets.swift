import AppKit
import Darwin

/// Лёгкие счётчики для строки меню: один пункт, обновление раз в N секунд с допуском таймера,
/// пауза, пока экран спит. Никакой фоновой работы, когда виджеты выключены.
final class Stats {
    private var lastTicks: (user: UInt64, system: UInt64, idle: UInt64, nice: UInt64)?
    private var lastNet: (rx: UInt64, tx: UInt64, time: Date)?

    /// Загрузка процессора 0…1 с прошлого вызова.
    func cpu() -> Double? {
        var info = host_cpu_load_info()
        var count = mach_msg_type_number_t(MemoryLayout<host_cpu_load_info_data_t>.size / MemoryLayout<integer_t>.size)
        let r = withUnsafeMutablePointer(to: &info) {
            $0.withMemoryRebound(to: integer_t.self, capacity: Int(count)) { host_statistics(mach_host_self(), HOST_CPU_LOAD_INFO, $0, &count) }
        }
        guard r == KERN_SUCCESS else { return nil }
        let t = (user: UInt64(info.cpu_ticks.0), system: UInt64(info.cpu_ticks.1), idle: UInt64(info.cpu_ticks.2), nice: UInt64(info.cpu_ticks.3))
        defer { lastTicks = t }
        guard let p = lastTicks else { return nil }
        let busy = Double((t.user &- p.user) &+ (t.system &- p.system) &+ (t.nice &- p.nice))
        let total = busy + Double(t.idle &- p.idle)
        return total > 0 ? busy / total : 0
    }

    /// Занятая память (активная + связанная + сжатая), байты.
    func memoryUsed() -> UInt64? {
        var vm = vm_statistics64()
        var count = mach_msg_type_number_t(MemoryLayout<vm_statistics64_data_t>.size / MemoryLayout<integer_t>.size)
        let r = withUnsafeMutablePointer(to: &vm) {
            $0.withMemoryRebound(to: integer_t.self, capacity: Int(count)) { host_statistics64(mach_host_self(), HOST_VM_INFO64, $0, &count) }
        }
        guard r == KERN_SUCCESS else { return nil }
        let page = UInt64(sysconf(_SC_PAGESIZE))
        let pages = UInt64(vm.active_count) + UInt64(vm.wire_count) + UInt64(vm.compressor_page_count)
        return pages * page
    }

    var memoryTotal: UInt64 { ProcessInfo.processInfo.physicalMemory }

    /// Скорость сети (байт/с) с прошлого вызова: приём, отдача.
    func network() -> (rx: Double, tx: Double)? {
        var rx: UInt64 = 0, tx: UInt64 = 0
        var addrs: UnsafeMutablePointer<ifaddrs>?
        guard getifaddrs(&addrs) == 0, let first = addrs else { return nil }
        defer { freeifaddrs(addrs) }
        var cur: UnsafeMutablePointer<ifaddrs>? = first
        while let ifa = cur {
            let flags = Int32(bitPattern: ifa.pointee.ifa_flags)
            if let addr = ifa.pointee.ifa_addr, addr.pointee.sa_family == UInt8(AF_LINK),
               flags & IFF_LOOPBACK == 0, flags & IFF_UP != 0, let data = ifa.pointee.ifa_data {
                let d = data.assumingMemoryBound(to: if_data.self).pointee
                rx += UInt64(d.ifi_ibytes)
                tx += UInt64(d.ifi_obytes)
            }
            cur = ifa.pointee.ifa_next
        }
        let now = Date()
        defer { lastNet = (rx, tx, now) }
        guard let p = lastNet else { return nil }
        let dt = max(0.1, now.timeIntervalSince(p.time))
        // счётчики 32-битные и могут переполняться — тогда считаем ноль
        let drx = rx >= p.rx ? Double(rx - p.rx) : 0
        let dtx = tx >= p.tx ? Double(tx - p.tx) : 0
        return (drx / dt, dtx / dt)
    }

    static func bytes(_ v: Double, perSecond: Bool = false) -> String {
        let units = ["Б", "КБ", "МБ", "ГБ", "ТБ"]
        var x = v, i = 0
        while x >= 1000 && i < units.count - 1 { x /= 1024; i += 1 }
        let s = x >= 100 || i == 0 ? String(format: "%.0f", x) : String(format: "%.1f", x)
        return "\(s) \(units[i])" + (perSecond ? "/с" : "")
    }
}

final class Widgets: NSObject, NSMenuDelegate {
    static let shared = Widgets()

    private let defaults = UserDefaults.standard
    private var item: NSStatusItem?
    private var timer: Timer?
    private let stats = Stats()
    private var asleep = false
    private var observers: [NSObjectProtocol] = []
    var onOpen: (() -> Void)?
    private var menuActions: [Action] = []

    var showCPU: Bool { get { defaults.bool(forKey: "w.cpu") } set { defaults.set(newValue, forKey: "w.cpu"); refresh() } }
    var showRAM: Bool { get { defaults.bool(forKey: "w.ram") } set { defaults.set(newValue, forKey: "w.ram"); refresh() } }
    var showNet: Bool { get { defaults.bool(forKey: "w.net") } set { defaults.set(newValue, forKey: "w.net"); refresh() } }
    var interval: Double {
        get { max(1, defaults.double(forKey: "w.interval") == 0 ? 2 : defaults.double(forKey: "w.interval")) }
        set { defaults.set(newValue, forKey: "w.interval"); refresh() }
    }

    var anyEnabled: Bool { showCPU || showRAM || showNet }

    func start() {
        let wnc = NSWorkspace.shared.notificationCenter
        observers.append(wnc.addObserver(forName: NSWorkspace.screensDidSleepNotification, object: nil, queue: .main) { [weak self] _ in
            self?.asleep = true
            self?.timer?.invalidate()
        })
        observers.append(wnc.addObserver(forName: NSWorkspace.screensDidWakeNotification, object: nil, queue: .main) { [weak self] _ in
            self?.asleep = false
            self?.refresh()
        })
        refresh()
    }

    /// Пересобирает пункт строки меню и таймер под текущие настройки.
    func refresh() {
        timer?.invalidate()
        timer = nil
        guard anyEnabled else {
            if let i = item { NSStatusBar.system.removeStatusItem(i) }
            item = nil
            return
        }
        if item == nil {
            let i = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
            let menu = NSMenu()
            menu.delegate = self
            i.menu = menu
            item = i
        }
        tick()
        guard !asleep else { return }
        let t = Timer(timeInterval: interval, repeats: true) { [weak self] _ in self?.tick() }
        t.tolerance = interval * 0.3  // macOS может объединять пробуждения — экономит батарею
        RunLoop.main.add(t, forMode: .common)
        timer = t
    }

    func text() -> String {
        var parts: [String] = []
        if showCPU { parts.append("CPU " + (stats.cpu().map { String(format: "%.0f%%", $0 * 100) } ?? "…")) }
        if showRAM {
            let used = stats.memoryUsed().map { Double($0) / 1_073_741_824 }
            parts.append("RAM " + (used.map { String(format: "%.1f/%.0f ГБ", $0, Double(stats.memoryTotal) / 1_073_741_824) } ?? "…"))
        }
        if showNet {
            if let n = stats.network() {
                parts.append("↓\(Stats.bytes(n.rx, perSecond: true)) ↑\(Stats.bytes(n.tx, perSecond: true))")
            } else {
                parts.append("↓… ↑…")
            }
        }
        return parts.joined(separator: "  ")
    }

    private func tick() {
        guard let button = item?.button else { return }
        let s = text()
        if button.title != s {
            button.attributedTitle = NSAttributedString(string: s, attributes: [.font: NSFont.monospacedDigitSystemFont(ofSize: 11.5, weight: .medium)])
        }
    }

    func menuNeedsUpdate(_ menu: NSMenu) {
        menu.removeAllItems()
        menuActions.removeAll()
        func add(_ title: String, _ key: String, _ fn: @escaping () -> Void) {
            let a = Action { _ in fn() }
            menuActions.append(a)
            let mi = NSMenuItem(title: title, action: #selector(Action.run(_:)), keyEquivalent: key)
            mi.target = a
            menu.addItem(mi)
        }
        add("Открыть TnQkoTweaks…", "") { [weak self] in self?.onOpen?() }
        add("Монитор активности", "") { NSWorkspace.shared.open(URL(fileURLWithPath: "/System/Applications/Utilities/Activity Monitor.app")) }
        menu.addItem(.separator())
        add("Выйти", "q") { NSApp.terminate(nil) }
    }
}
