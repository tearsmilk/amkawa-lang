import CoreGraphics
import Foundation

enum Judgement: Int, CaseIterable {
    case miss = 0, h50 = 50, h100 = 100, h300 = 300

    var text: String {
        switch self {
        case .miss: return "✕"
        case .h50: return "50"
        case .h100: return "100"
        case .h300: return "300"
        }
    }
}

struct Popup {
    let judgement: Judgement
    let pos: CGPoint
    let time: Double
}

/// Состояние объекта во время игры.
struct ObjectState {
    var result: Judgement?
    var resultTime: Double = 0
    var headHit: Bool?          // слайдер: попали ли в голову
    var headTime: Double = 0
    var tracking = false        // слайдер: держим ли шар сейчас
    var tracked: Double = 0     // мс удержания
    var lastUpdate: Double?
    var spin: Double = 0        // спиннер: накопленный угол, рад
    var lastAngle: Double?
}

/// Правила игры без отрисовки: удары, слайдеры, спиннеры, комбо, здоровье, счёт.
final class GameSession {
    let map: Beatmap
    let diff: Difficulty
    var noFail = false
    var onHit: ((Judgement) -> Void)?
    var onComboBreak: (() -> Void)?

    private(set) var score = 0
    private(set) var combo = 0
    private(set) var maxCombo = 0
    private(set) var counts: [Judgement: Int] = [.h300: 0, .h100: 0, .h50: 0, .miss: 0]
    private(set) var hp = 1.0
    private(set) var failed = false
    private(set) var popups: [Popup] = []
    private(set) var states: [ObjectState]
    private(set) var nextIndex = 0
    private var lastTime: Double?
    private let scoreMultiplier: Double

    static let spinCenter = CGPoint(x: 256, y: 192)

    init(map: Beatmap) {
        self.map = map
        diff = map.difficulty
        states = Array(repeating: ObjectState(), count: map.objects.count)
        scoreMultiplier = max(2, min(6, ((diff.hp + diff.cs + diff.od) / 38 * 5).rounded()))
    }

    var radius: Double { diff.radius }
    var endTime: Double { map.endTime }
    var finished: Bool { nextIndex >= map.objects.count }
    var judgedCount: Int { counts.values.reduce(0, +) }

    var accuracy: Double {
        let n = Double(judgedCount)
        guard n > 0 else { return 1 }
        let pts = 300 * Double(counts[.h300]!) + 100 * Double(counts[.h100]!) + 50 * Double(counts[.h50]!)
        return pts / (300 * n)
    }

    var grade: String {
        let n = Double(max(1, judgedCount))
        let r300 = Double(counts[.h300]!) / n
        let r50 = Double(counts[.h50]!) / n
        let misses = counts[.miss]!
        if judgedCount > 0 && counts[.h300]! == judgedCount { return "SS" }
        if r300 > 0.9 && r50 < 0.01 && misses == 0 { return "S" }
        if (r300 > 0.8 && misses == 0) || r300 > 0.9 { return "A" }
        if (r300 > 0.7 && misses == 0) || r300 > 0.8 { return "B" }
        if r300 > 0.6 { return "C" }
        return "D"
    }

    // MARK: ввод

    /// Нажатие (клавиша или кнопка мыши) в момент t, курсор в osu!-координатах. Возвращает, попали ли.
    @discardableResult
    func press(at t: Double, pos: CGPoint) -> Bool {
        guard !failed else { return false }
        // «notelock»: бить можно только первый ещё не отбитый объект
        var i = nextIndex
        while i < map.objects.count {
            let o = map.objects[i]
            let s = states[i]
            if o.kind == .circle && s.result == nil { break }
            if o.kind == .slider && s.headHit == nil { break }
            i += 1
            if i - nextIndex > 8 { return false }
        }
        guard i < map.objects.count else { return false }
        let o = map.objects[i]
        guard t >= o.time - diff.window50 - 150 else { return false }  // слишком рано — игнор
        let dist = Double(hypot(pos.x - o.pos.x, pos.y - o.pos.y))
        guard dist <= radius else { return false }
        let delta = abs(t - o.time)
        if t < o.time - diff.window50 {
            // ранний тык рядом с кружком — промах, как в osu!
            if o.kind == .circle { judge(i, .miss, at: o.pos, t: t) } else { sliderHead(i, hit: false, t: t) }
            return false
        }
        if o.kind == .circle {
            let j: Judgement = delta <= diff.window300 ? .h300 : delta <= diff.window100 ? .h100 : .h50
            judge(i, j, at: o.pos, t: t)
        } else {
            sliderHead(i, hit: true, t: t)
        }
        return true
    }

    /// Кадр: авто-промахи, слайдеры, спиннеры, здоровье. held — зажата ли любая клавиша/кнопка.
    func update(t: Double, cursor: CGPoint, held: Bool) {
        let dt = max(0, min(100, t - (lastTime ?? t)))
        lastTime = t
        guard !failed else { return }
        var i = nextIndex
        while i < map.objects.count {
            let o = map.objects[i]
            if o.time - diff.preempt > t { break }
            switch o.kind {
            case .circle:
                if states[i].result == nil && t > o.time + diff.window50 { judge(i, .miss, at: o.pos, t: t) }
            case .slider:
                updateSlider(i, o, t: t, cursor: cursor, held: held)
            case .spinner:
                updateSpinner(i, o, t: t, cursor: cursor, held: held)
            }
            i += 1
        }
        while nextIndex < map.objects.count && states[nextIndex].result != nil { nextIndex += 1 }

        // здоровье: медленно убывает, пока впереди есть объекты (в паузах-перерывах не убывает)
        if nextIndex < map.objects.count, t >= map.firstTime {
            let upcoming = map.objects[nextIndex].time - t
            let active = map.objects[nextIndex].kind != .circle && t >= map.objects[nextIndex].time
            if upcoming < 2500 || active { hp -= dt / 1000 * (0.02 + 0.004 * diff.hp) }
        }
        hp = max(0, min(1, hp))
        if hp <= 0 && !noFail { failed = true }
        popups.removeAll { t - $0.time > 700 }
    }

    private func updateSlider(_ i: Int, _ o: HitObject, t: Double, cursor: CGPoint, held: Bool) {
        if states[i].headHit == nil && t > o.time + diff.window50 { sliderHead(i, hit: false, t: t) }
        guard states[i].result == nil, t >= o.time else { return }
        let from = states[i].lastUpdate ?? o.time
        let now = min(t, o.endTime)
        let ball = o.sliderPosition(at: now)
        let follow = states[i].tracking ? radius * 2.4 : radius
        let inside = Double(hypot(cursor.x - ball.x, cursor.y - ball.y)) <= follow
        let wasTracking = states[i].tracking
        states[i].tracking = held && inside
        if states[i].tracking { states[i].tracked += max(0, now - from) }
        if wasTracking && !states[i].tracking && now < o.endTime - 30 && combo > 0 {
            combo = 0
            onComboBreak?()
        }
        states[i].lastUpdate = now
        if t >= o.endTime {
            let ratio = states[i].tracked / max(1, o.duration)
            let head = states[i].headHit == true
            let j: Judgement
            if head && ratio >= 0.85 { j = .h300 } else if ratio >= 0.5 || (head && ratio >= 0.3) { j = .h100 } else if head || ratio > 0.1 { j = .h50 } else { j = .miss }
            states[i].tracking = false
            judge(i, j, at: o.endPosition, t: t)
        }
    }

    private func updateSpinner(_ i: Int, _ o: HitObject, t: Double, cursor: CGPoint, held: Bool) {
        guard states[i].result == nil else { return }
        if t >= o.time && t <= o.endTime && held {
            let angle = atan2(Double(cursor.y - Self.spinCenter.y), Double(cursor.x - Self.spinCenter.x))
            if let last = states[i].lastAngle {
                var d = angle - last
                while d > .pi { d -= 2 * .pi }
                while d < -.pi { d += 2 * .pi }
                states[i].spin += min(abs(d), .pi / 2)
            }
            states[i].lastAngle = angle
        } else {
            states[i].lastAngle = nil
        }
        if t > o.endTime {
            let need = spinsRequired(o)
            let got = states[i].spin / (2 * .pi)
            let j: Judgement = got >= need ? .h300 : got >= need * 0.6 ? .h100 : got >= need * 0.25 ? .h50 : .miss
            judge(i, j, at: Self.spinCenter, t: t)
        }
    }

    func spinsRequired(_ o: HitObject) -> Double {
        max(1, o.duration / 1000 * (0.9 + diff.od * 0.12))
    }

    private func sliderHead(_ i: Int, hit: Bool, t: Double) {
        states[i].headHit = hit
        states[i].headTime = t
        if hit {
            combo += 1
            maxCombo = max(maxCombo, combo)
            score += 30
            onHit?(.h300)
        } else if combo > 0 {
            combo = 0
            onComboBreak?()
        }
    }

    private func judge(_ i: Int, _ j: Judgement, at pos: CGPoint, t: Double) {
        states[i].result = j
        states[i].resultTime = t
        counts[j, default: 0] += 1
        if j == .miss {
            if combo >= 10 { onComboBreak?() }
            combo = 0
            hp -= 0.06 + 0.012 * diff.hp
        } else {
            score += Int(Double(j.rawValue) * (1 + Double(max(0, combo - 1)) * scoreMultiplier / 25))
            combo += 1
            maxCombo = max(maxCombo, combo)
            hp += j == .h300 ? 0.05 : j == .h100 ? 0.02 : 0.005
            onHit?(j)
        }
        hp = max(0, min(1, hp))
        popups.append(Popup(judgement: j, pos: pos, time: t))
    }

    /// Идеальная игра для самопроверки: нажатия ровно в такт, курсор следует за шаром, спиннеры крутятся.
    static func autoplay(_ session: GameSession, step: Double = 8) {
        let objects = session.map.objects
        guard let last = objects.last else { return }
        var t = session.map.firstTime - 1000
        var next = 0
        var angle = 0.0
        let end = session.endTime + 500
        _ = last
        while t <= end {
            var cursor = CGPoint(x: 256, y: 192)
            var held = false
            if let active = objects.first(where: { $0.time <= t && t <= $0.endTime && $0.kind != .circle }) {
                held = true
                if active.kind == .slider {
                    cursor = active.sliderPosition(at: t)
                } else {
                    angle += 0.5
                    cursor = CGPoint(x: 256 + 80 * cos(angle), y: 192 + 80 * sin(angle))
                }
            }
            while next < objects.count && objects[next].kind == .spinner { next += 1 }
            if next < objects.count && t >= objects[next].time {
                session.press(at: objects[next].time, pos: objects[next].pos)
                next += 1
                while next < objects.count && objects[next].kind == .spinner { next += 1 }
            }
            session.update(t: t, cursor: cursor, held: held)
            t += step
        }
    }
}
