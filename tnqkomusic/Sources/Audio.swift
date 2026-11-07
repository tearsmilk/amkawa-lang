import AVFoundation

/// Музыка + игровые часы. Время берётся из часов аудиоустройства — оно не «дрожит» и не уплывает от звука.
final class MusicClock {
    let player: AVAudioPlayer
    private var startDevice: TimeInterval = 0
    private var pausedAt: Double = 0
    private(set) var isRunning = false
    /// Пользовательское смещение, мс: положительное — удары засчитываются позже.
    var offsetMs: Double = 0

    init(url: URL) throws {
        player = try AVAudioPlayer(contentsOf: url)
        player.prepareToPlay()
    }

    var duration: Double { player.duration }

    var volume: Float {
        get { player.volume }
        set { player.volume = newValue }
    }

    var seconds: Double { isRunning ? player.deviceCurrentTime - startDevice : pausedAt }
    var timeMs: Double { seconds * 1000 - offsetMs }

    /// Запуск с позиции (сек); отрицательная позиция — вступление до начала трека.
    func start(from s: Double) {
        let now = player.deviceCurrentTime
        if s < 0 {
            player.currentTime = 0
            player.play(atTime: now - s)
            startDevice = now - s
        } else if s >= player.duration {
            player.stop()
            startDevice = now - s
        } else {
            let lead = 0.03
            player.currentTime = s
            player.play(atTime: now + lead)
            startDevice = now + lead - s
        }
        isRunning = true
    }

    func pause() {
        guard isRunning else { return }
        pausedAt = seconds
        player.pause()
        isRunning = false
    }

    func resume() { start(from: pausedAt) }

    func stop() {
        player.stop()
        isRunning = false
    }
}

/// Короткий «тик» при попадании: синтезируется, играется через AVAudioEngine с несколькими голосами.
final class HitSounds {
    private let engine = AVAudioEngine()
    private var voices: [AVAudioPlayerNode] = []
    private var hit: AVAudioPCMBuffer?
    private var miss: AVAudioPCMBuffer?
    private var next = 0
    var volume: Float = 0.6

    init() {
        guard let format = AVAudioFormat(standardFormatWithSampleRate: 44100, channels: 1) else { return }
        // без устройства вывода (CI, отключённые колонки) движок не трогаем: AVAudioEngine бросит исключение
        let out = engine.outputNode.outputFormat(forBus: 0)
        guard out.channelCount > 0, out.sampleRate > 0 else { return }
        hit = Self.synth(format, seconds: 0.07) { t in
            (sin(2 * .pi * 1760 * t) * 0.45 + sin(2 * .pi * 880 * t) * 0.35 + Double.random(in: -1...1) * 0.25 * exp(-t * 200)) * exp(-t * 60)
        }
        miss = Self.synth(format, seconds: 0.25) { t in
            sin(2 * .pi * (220 - 300 * t) * t) * 0.5 * exp(-t * 12)
        }
        for _ in 0..<8 {
            let node = AVAudioPlayerNode()
            engine.attach(node)
            engine.connect(node, to: engine.mainMixerNode, format: format)
            voices.append(node)
        }
        engine.prepare()
        try? engine.start()
    }

    var isReady: Bool { engine.isRunning && hit != nil }

    func playHit() { play(hit, gain: 1) }
    func playComboBreak() { play(miss, gain: 0.8) }

    private func play(_ buffer: AVAudioPCMBuffer?, gain: Float) {
        guard engine.isRunning, let b = buffer, !voices.isEmpty, volume > 0 else { return }
        let node = voices[next]
        next = (next + 1) % voices.count
        node.volume = volume * gain
        node.scheduleBuffer(b, at: nil, options: .interrupts, completionHandler: nil)
        if !node.isPlaying { node.play() }
    }

    static func synth(_ format: AVAudioFormat, seconds: Double, _ f: (Double) -> Double) -> AVAudioPCMBuffer? {
        let frames = AVAudioFrameCount(format.sampleRate * seconds)
        guard let buf = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: frames), let data = buf.floatChannelData?[0] else { return nil }
        buf.frameLength = frames
        for i in 0..<Int(frames) {
            let t = Double(i) / format.sampleRate
            let fade = min(1, Double(Int(frames) - i) / 200)
            data[i] = Float(max(-1, min(1, f(t) * fade)))
        }
        return buf
    }
}
